"""
FastAPI wrapper for the Inheco incubator Python interface.
"""

import argparse
import logging
import threading
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Query, Request

from inheco_incubator_interface import Interface
from pydantic_models import (
    SetShakerParametersRequest,
    StartShakerRequest,
    TemperatureRequest,
)

device = None  # singleton interface instance
app = FastAPI()
config = {}
cached_states = {}
device_lock = threading.Lock()

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename="inheco_FastAPI.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# GENERAL ACTIONS
def create_app(device: int, dll_path: str) -> FastAPI:
    """
    Creates the app and opens the connection to the specified COM port.

    Args:
        device (int): COM port for the incubator device(s).
        dll_path (str): Path to the Inheco device DLL.

    Returns:
        FastAPI: The FastAPI application instance."""
    config["device"] = device
    config["dll_path"] = dll_path
    return app


def get_device(request: Request) -> Interface:
    """
    Dependency to get the device instance.

    Args:
        request (Request): FastAPI request object.

    Returns:
        Interface: The device interface instance.
    """
    return request.app.state.device


@app.get("/")
def read_root() -> dict[str, str]:
    """
    Displays a message on root endpoint.
    """
    return {"message": f"Running with device(s) on COM port {config['device']}."}


@app.on_event("startup")
async def startup_event() -> None:
    """
    Called on start up of the FAST API. Initializes the device interface.
    """
    global device  # noqa PLW0603
    with device_lock:
        try:
            device = Interface(port=config["device"], dll_path=config["dll_path"])
        except Exception as e:
            raise (e)


@app.get(
    "/initialize", summary="Initializes the incubator at the specified stack_floor."
)
def initialize(stack_floor: int = Query(..., description="Stack floor number")) -> None:
    """
    Initializes the device.
    """
    device.initialize_device(stack_floor=stack_floor)
    logger.info(f"Device initialized at stack floor {stack_floor}.")


@app.get("/reset", summary="Resets the incubator at the specified stack_floor.")
def reset(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Resets the device.
    """
    device.reset_device(stack_floor=stack_floor)
    logger.info(f"Device reset at stack floor {stack_floor}.")


@app.get(
    "/report_error_flags",
    summary="Reports any error flags present on incubator at specified stack_floor (0 = no errors).",
)
def report_error_flags(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> str:
    """
    Reports any error flags present.
    """
    response = device.report_error_flags(stack_floor=stack_floor)
    logger.info(f"Reported error flags @ stack floor {stack_floor}: {response}.")
    return response


# STATE HANDLER
@app.get(
    "/get_state",
    summary="Returns the state of the incubator device at the specified stack_floor.",
)
def get_state(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> dict[str, Optional[Any]]:
    """
    Returns the incubator state.
    """
    logger.info("Getting state.")

    if stack_floor in cached_states:
        if not device.is_busy:
            # Query the device for fresh state information and add to cached state.
            cached_states[stack_floor] = {
                "target_temp": device.get_target_temperature(stack_floor=stack_floor),
                "actual_temp": device.get_actual_temperature(stack_floor=stack_floor),
                "shaker_active": device.is_shaker_active(stack_floor=stack_floor),
                "heater_active": device.is_heater_active(stack_floor=stack_floor),
            }
            logger.debug(
                f"Device known, not busy. state = {cached_states[stack_floor]}"
            )
    elif device.is_busy:
        # Save empty state information into cached states.
        cached_states[stack_floor] = {
            "target_temp": None,
            "actual_temp": None,
            "shaker_active": None,
            "heater_active": None,
        }
        logger.debug(f"device unknown and busy. state = {cached_states[stack_floor]}")
    else:
        # Query device for state information and save to cached states.
        cached_states[stack_floor] = {
            "target_temp": device.get_target_temperature(stack_floor=stack_floor),
            "actual_temp": device.get_actual_temperature(stack_floor=stack_floor),
            "shaker_active": device.is_shaker_active(stack_floor=stack_floor),
            "heater_active": device.is_heater_active(stack_floor=stack_floor),
        }
        logger.debug(f"Device unknown, not busy. state = {cached_states[stack_floor]}")
    return cached_states[stack_floor]


# DOOR ACTIONS
@app.get("/open_door", summary="Opens the incubator door at specified stack_floor.")
def open_door(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Opens the door.
    """
    device.open_door(stack_floor=stack_floor)
    logger.info(f"Door opened at stack floor {stack_floor}.")


@app.get("/close_door", summary="Closes the incubator door at specified stack_floor.")
def close_door(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Closes the door.
    """
    device.close_door(stack_floor=stack_floor)
    logger.info(f"Door closed at stack floor {stack_floor}.")


@app.get(
    "/report_door_status",
    summary="Reports door status at specified stack floor, 0 closed, 1 open.",
)
def report_door_status(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> str:
    """
    Reports the door status.

    Returns: (str) door status
        0 = door closed
        1 = door open
    """
    door_status = device.report_door_status(stack_floor=stack_floor)
    logger.info(f"Door status at stack floor {stack_floor}: {door_status}.")
    return door_status


@app.get(
    "/report_labware",
    summary="Reports if labware is present at the specified stack floor.",
)
def report_labware(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> str:
    """
    Reports the labware status.

    Returns: (str) Labware status.
        0 = no labware present
        1 = labware detected
        8 = error, door open
        7 = error, reset and door closed
    """
    labware_status = device.report_door_status(stack_floor=stack_floor)
    logger.info(f"Report labware at stack floor {stack_floor}: {labware_status}.")
    return labware_status


# TEMPERATURE ACTIONS
@app.get(
    "/get_actual_temperature",
    summary="Returns the actual temperature of the incubator at the specified stack floor.",
)
def get_actual_temperature(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> float:
    """
    Returns the actual temperature.
    """
    temperature = device.get_actual_temperature(stack_floor=stack_floor)
    logger.info(f"Actual temperature at stack floor {stack_floor}: {temperature}.")
    return temperature


@app.get(
    "/get_target_temperature",
    summary="Returns the target temperature of the incubator at the specified stack floor.",
)
def get_target_temperature(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> float:
    """
    Returns the target temperature.
    """
    temperature = device.get_target_temperature(stack_floor=stack_floor)
    logger.info(f"Target temperature at stack floor {stack_floor}: {temperature}.")
    return temperature


@app.post(
    "/set_target_temperature",
    summary="Sets the target temperature of the incubator at the specified stack floor.",
)
def set_target_temperature(
    request: TemperatureRequest,
) -> None:
    """
    Sets the target temperature.
    """
    device.set_target_temperature(
        stack_floor=request.stack_floor, temperature=request.temperature
    )
    logger.info(
        f"Temperature set at stack floor {request.stack_floor}: {request.temperature}."
    )


# HEATER ACTIONS
@app.get(
    "/start_heater",
    summary="Turns on the incubator heater at the specified stack floor.",
)
def start_heater(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Starts the heater.
    """
    device.start_heater(stack_floor=stack_floor)
    logger.info(f"Heater started at stack floor {stack_floor}.")


@app.get(
    "/stop_heater",
    summary="Turns off the incubator heater at the specified stack floor.",
)
def stop_heater(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Stops the heater.
    """
    device.stop_heater(stack_floor=stack_floor)
    logger.info(f"Heater stopped at stack floor {stack_floor}.")


@app.get(
    "/is_heater_active",
    summary="Reports the status of the heater at the specified stack floor.",
)
def is_heater_active(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> bool:
    """
    Reports heater status.

    Returns: (bool) True if heater/cooler is activated, otherwise False.
    """
    response = device.is_heater_active(stack_floor=stack_floor)
    logger.info(f"Heater status at stack floor {stack_floor}: {response}.")
    return response


# SHAKER COMMANDS
@app.post("/start_shaker", summary="Starts shaker at the specified stack floor.")
def start_shaker(
    request: StartShakerRequest,
) -> None:
    """
    Starts the shaker.
    """
    device.start_shaker(stack_floor=request.stack_floor, status=request.status)
    logger.info(f"Shaker started at stack floor {request.stack_floor}.")


@app.get("/stop_shaker", summary="Stops shaker at the specified stack floor.")
def stop_shaker(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> None:
    """
    Stops the shaker.
    """
    device.stop_shaker(stack_floor=stack_floor)
    logger.info(f"Shaker stopped at stack floor {stack_floor}.")


@app.get(
    "/is_shaker_active",
    summary="Determines if the shaker is active at the specified stack floor (True = active, False = inactive).",
)
def is_shaker_active(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> bool:
    """
    Determines if shaker is active.

    Returns: (bool) True if shaker is activated, otherwise False.
    """
    response = device.is_shaker_active(stack_floor=stack_floor)
    logger.info(f"Shaker status at stack floor {stack_floor}: {response}.")
    return response


@app.post(
    "/set_shaker_parameters",
    summary="Sets the shaker parameters at the specified stack floor.",
)
def set_shaker_parameters(
    request: SetShakerParametersRequest,
) -> None:
    """
    Sets the shaker parameters.
    """
    device.set_shaker_parameters(
        stack_floor=request.stack_floor, frequency=request.frequency
    )
    logger.info(
        f"Shaker parameters set at stack floor {request.stack_floor}: frequency = {request.frequency}."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host computer IP for the interface API.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="COM5",
        help="COM Port for the incubator device(s).",
    )
    parser.add_argument(
        "--port", type=int, default=7000, help="Port to run FastAPI on."
    )
    parser.add_argument(
        "--dll_path",
        type=str,
        help="Path to inheco device dll.",
        default="C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
    )

    args = parser.parse_args()

    app = create_app(device=args.device, dll_path=args.dll_path)
    uvicorn.run(app, host=args.host, port=args.port)
