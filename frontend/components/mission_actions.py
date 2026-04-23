import threading

from components.state import (
    ARRIVAL_TIMES_BY_MODE,
    MISSION_UGV_PLAN_BY_MODE,
    active_btn,
    asset_data,
    mission_delivery_data,
    departure_times,
    mission_settings,
    operating_ugv_plan,
    selected_mission_mode,
    toast_trigger,
)

from services.api_client import (
    auth_token,
    user_role,
    post_operator_mission_config,
    fetch_all_operator_briefings,
    resolve_destination_coordinate_for_unit,
)

def deliver_mission():
    current_mode = selected_mission_mode.value or active_btn.value or "균형"
    current_mode = selected_mission_mode.value or mission_settings.value.get("mode") or active_btn.value or "균형"
    current_arrival_times = ARRIVAL_TIMES_BY_MODE.get(current_mode, {})

    mission_delivery_data.value = {
        "delivered": True,
        "base_summary": {
            "total_units": asset_data.value.get("base", {}).get("total_units", 0),
            "total_controllers": asset_data.value.get("base", {}).get("total_controllers", 0),
            "total_ugv": asset_data.value.get("base", {}).get("total_ugv", 0),
            "total_recon_ugv": asset_data.value.get("base", {}).get("total_ugv", 0),
            "total_lost_ugv": asset_data.value.get("base", {}).get("lost_ugv", 0),
        },
        "units": {
            u: {
                "controllers": asset_data.value.get(u, {}).get("controllers", 0),
                "total_ugv": asset_data.value.get(u, {}).get("total_ugv", 0),
                "total_recon_ugv": asset_data.value.get(u, {}).get("total_ugv", 0),
                "lost_ugv": asset_data.value.get(u, {}).get("lost_ugv", 0),
                "available_ugv": asset_data.value.get(u, {}).get("available_ugv", 0),
                "target_lat": resolve_destination_coordinate_for_unit(u, "lat", current_mode) or asset_data.value.get(u, {}).get("target_lat", ""),
                "target_lon": resolve_destination_coordinate_for_unit(u, "lon", current_mode) or asset_data.value.get(u, {}).get("target_lon", ""),
            }
            for u in ("user1", "user2", "user3")
        },
        "mission_info": {
            u: {
                "mission_mode": current_mode,
                "operating_ugv_count": operating_ugv_plan.value.get(u)
                or MISSION_UGV_PLAN_BY_MODE.get(current_mode, {}).get(
                    u, asset_data.value.get(u, {}).get("available_ugv", 0)
                ),
                "departure_time": departure_times.value.get(u) or mission_settings.value.get("depart_times", {}).get(u, "03:00:00"),
                "arrival_time": current_arrival_times.get(u, ""),
                "recon_time": mission_settings.value.get("recon_times", {}).get(u, ""),
            }
            for u in ("user1", "user2", "user3")
        },
    }

    if auth_token.value and user_role.value == "commander":
        post_operator_mission_config()
        fetch_all_operator_briefings()
    else:
        threading.Thread(target=post_operator_mission_config, daemon=True).start()
    toast_trigger.value += 1
