"""
backend/app/simulation/algo/environment.py

mumt_sim Environment — 백엔드 통합용 수정본.

원본 대비 변경 사항:
  - load_all_data(): 실제 파일명(단일 타임스탬프, 서브디렉토리) 형식 지원
  - 서버 연동을 방해하는 print문을 logging으로 교체
"""

import logging
import pandas as pd
import numpy as np
import glob
import os
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Environment:
    def __init__(self, config):
        self.config = config
        self.static_file = config.TERRAIN_PATH
        self.dynamic_dir = config.DYNAMIC_DIR
        self.grid_size = config.GRID_SIZE
        self.ny, self.nx = self.grid_size

        self.sim_time = None
        self.current_model_time = None

        self.base_layer = np.ones(self.grid_size, dtype=np.float32)
        self.global_time_pool = {}
        self.actual_data_pool = {}
        self.active_layers = np.zeros((18, self.ny, self.nx), dtype=np.float32)

        self.comm_mask = np.zeros((self.ny, self.nx), dtype=np.int8)

        self.lc_cost_map = {
            10: 2.5, 20: 1.5, 30: 1.0, 40: 1.2, 50: 999,
            60: 1.1, 80: 999, 90: 999, 100: 2.0
        }

        self.masks = {
            f"mask_{r*2:02d}km": self._create_circular_mask(radius=r)
            for r in range(1, 11)
        }

        self.mask_02km = self.masks["mask_02km"]
        self.mask_04km = self.masks["mask_04km"]
        self.mask_06km = self.masks["mask_06km"]
        self.mask_08km = self.masks["mask_08km"]
        self.mask_10km = self.masks["mask_10km"]
        self.mask_12km = self.masks["mask_12km"]
        self.mask_14km = self.masks["mask_14km"]
        self.mask_16km = self.masks["mask_16km"]
        self.mask_18km = self.masks["mask_18km"]
        self.mask_20km = self.masks["mask_20km"]

        # manned_pos는 UGV가 RECALL 모드일 때 참조용 (MannedVehicle.pos 동기화)
        self.manned_pos = np.array([0, 0], dtype=float)

    def _create_circular_mask(self, radius):
        y, x = np.ogrid[-radius: radius + 1, -radius: radius + 1]
        return x ** 2 + y ** 2 <= radius ** 2

    def get_layer_idx(self, target_time):
        if self.current_model_time is None:
            return 0
        delta = target_time - self.current_model_time
        idx = int(delta.total_seconds() / 600)
        return max(0, min(idx, 17))

    def update_forecast_model(self, new_model_time):
        self.current_model_time = new_model_time
        logger.debug("예보 모델 업데이트: %s", new_model_time.strftime('%H:%M'))

    def load_base_layer(self):
        if not os.path.exists(self.static_file):
            raise FileNotFoundError(f"지형 파일 없음: {self.static_file}")

        df = pd.read_parquet(self.static_file)
        grid = np.zeros(self.grid_size, dtype=np.float32)

        rows = df['row'].values.astype(int)
        cols = df['col'].values.astype(int)
        codes = df['lc_code'].values

        mask = (rows < self.ny) & (cols < self.nx)
        grid[rows[mask], cols[mask]] = codes[mask]

        self.base_layer = np.vectorize(
            lambda x: self.lc_cost_map.get(int(x), 1.0)
        )(grid).astype(np.float32)
        logger.info("base_layer 로드 완료 shape=%s", self.base_layer.shape)
        return self.base_layer

    def load_all_data(self):
        """
        dynamic_dir 하위(서브디렉토리 포함)의 모든 .parquet 파일을 로드.
        파일명에서 타임스탬프를 추출하여 actual_data_pool에 저장.

        파일명 형식:
          sim_cost_map_20230715_1200_10x10.parquet  (타임스탬프 1개)
          또는
          forecast_20230715_1200_20230715_1210.parquet (타임스탬프 2개)
        """
        # 서브디렉토리까지 재귀 탐색
        file_pattern = os.path.join(self.dynamic_dir, "**", "*.parquet")
        files = sorted(glob.glob(file_pattern, recursive=True))
        if not files:
            # 직접 디렉토리 탐색 폴백
            file_pattern = os.path.join(self.dynamic_dir, "*.parquet")
            files = sorted(glob.glob(file_pattern))

        logger.info("dynamic 파일 %d개 로드 시작", len(files))

        for f in files:
            basename = os.path.basename(f)
            times = re.findall(r'\d{8}_\d{4}', basename)
            if not times:
                continue

            try:
                df_t = pd.read_parquet(f)
                # tactical_cost 컬럼이 없으면 첫 번째 숫자 컬럼 사용
                if 'tactical_cost' in df_t.columns:
                    values = df_t['tactical_cost'].values
                else:
                    num_cols = df_t.select_dtypes(include=[np.number]).columns
                    if len(num_cols) == 0:
                        continue
                    values = df_t[num_cols[0]].values

                expected = self.ny * self.nx
                if len(values) < expected:
                    logger.warning("파일 크기 불일치 %s: %d vs %d", basename, len(values), expected)
                    # 부족한 부분은 0으로 패딩
                    padded = np.zeros(expected, dtype=np.float32)
                    padded[:len(values)] = values.astype(np.float32)
                    grid_t = padded.reshape(self.ny, self.nx)
                elif len(values) > expected:
                    grid_t = values[:expected].astype(np.float32).reshape(self.ny, self.nx)
                else:
                    grid_t = values.astype(np.float32).reshape(self.ny, self.nx)

                # 타임스탬프 2개면 forecast, 1개면 actual
                target_t = datetime.strptime(times[-1], '%Y%m%d_%H%M')

                if len(times) >= 2:
                    model_t = datetime.strptime(times[0], '%Y%m%d_%H%M')
                    self.global_time_pool[(model_t, target_t)] = grid_t
                else:
                    self.actual_data_pool[target_t] = grid_t

            except Exception as e:
                logger.warning("파일 로드 실패 %s: %s", basename, e)

        logger.info(
            "동적 데이터 로드 완료: actual=%d, forecast=%d",
            len(self.actual_data_pool), len(self.global_time_pool)
        )

    def get_active_time_cube(self):
        layers = []
        for i in range(18):
            target_t = self.sim_time + timedelta(minutes=i * 10)
            if i == 0:
                layer = self.actual_data_pool.get(
                    target_t, np.zeros(self.grid_size, dtype=np.float32)
                )
            else:
                layer = self.global_time_pool.get(
                    (self.current_model_time, target_t),
                    np.zeros(self.grid_size, dtype=np.float32)
                )
                # forecast 없으면 actual로 폴백
                if not np.any(layer):
                    layer = self.actual_data_pool.get(
                        target_t, np.zeros(self.grid_size, dtype=np.float32)
                    )
            layers.append(layer)

        self.active_layers = np.stack(layers, axis=0)
        return self.active_layers

    def update_comm_mask(self, manned_pos):
        self.comm_mask.fill(0)
        self.manned_pos = np.array(manned_pos, dtype=float)
        cy, cx = int(manned_pos[0]), int(manned_pos[1])
        self._apply_mask_to_grid(cy, cx, self.mask_18km, value=1)
        self._apply_mask_to_grid(cy, cx, self.mask_12km, value=2)

    def _apply_mask_to_grid(self, cy, cx, mask, value):
        r = mask.shape[0] // 2
        y_min = max(0, cy - r)
        y_max = min(self.ny, cy + r + 1)
        x_min = max(0, cx - r)
        x_max = min(self.nx, cx + r + 1)

        my_min = y_min - (cy - r)
        my_max = my_min + (y_max - y_min)
        mx_min = x_min - (cx - r)
        mx_max = mx_min + (x_max - x_min)

        valid_mask = mask[my_min:my_max, mx_min:mx_max]
        target_area = self.comm_mask[y_min:y_max, x_min:x_max]
        target_area[valid_mask] = value
