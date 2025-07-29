"""
FastAPI wrapper for Inheco incubator interface
"""

import argparse
import logging
import threading

import uvicorn
from fastapi import FastAPI, Query

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
def create_app(device: int, dll_path: str):
    """Created the app and opens connection to the specified COM port"""
    global config
    config["device"] = device
    config["dll_path"] = dll_path
    return app


@app.get("/")
def read_root():
    """Displays message on root endpoint"""
    return {"message": f"Running with device(s) on COM port {config['device']}"}


@app.on_event("startup")
async def startup_event():
    "Called on start up of the FAST API"
    # TODO: app.on_event deprecated. switch to lifespan events
    global device
    with device_lock:
        try:
            device = Interface(port=config["device"], dll_path=config["dll_path"])
        except Exception as e:
            raise (e)


@app.get("/initialize", summary="initializes incubator at specified stack_floor")
def initialize(stack_floor: int = Query(..., description="Stack floor number")):
    """Initializes the device"""
    device.initialize_device(stack_floor=stack_floor)
    logger.info(f"device initialized @ stack floor {stack_floor}")


@app.get("/reset", summary="resets the incubator at specified stack_floor")
def reset(stack_floor: int = Query(..., description="Stack floor number")):
    """Resets the device"""
    device.reset_device(stack_floor=stack_floor)
    logger.info(f"device reset @ stack floor {stack_floor}")


@app.get(
    "/report_error_flags",
    summary="reports any error flags present on incubator at specified stack_floor (0 = no errors)",
)
def report_error_flags(stack_floor: int = Query(..., description="Stack floor number")):
    """Reports any error flags present"""
    response = device.report_error_flags(stack_floor=stack_floor)
    logger.info(f"Reported error flags @ stack floor {stack_floor}: {response}")
    return response


# STATE HANDLER
@app.get(
    "/get_state",
    summary="returns the state of incubator device at the specified stack_floor",
)
def get_state(stack_floor: int = Query(..., description="Stack floor number")):
    """Returns the incubator state"""
    logger.info("getting state")

    if stack_floor in cached_states:
        if not device.is_busy:
            # query device for fresh state information and add to cached state
            cached_states[stack_floor] = {
                "target_temp": device.get_target_temperature(stack_floor=stack_floor),
                "actual_temp": device.get_actual_temperature(stack_floor=stack_floor),
                "shaker_active": device.is_shaker_active(stack_floor=stack_floor),
                "heater_active": device.is_heater_active(stack_floor=stack_floor),
            }
            logger.debug(
                f"device known, not busy. state = {cached_states[stack_floor]}"
            )
    else:
        if device.is_busy:
            # save empty state information into cached states
            cached_states[stack_floor] = {
                "target_temp": None,
                "actual_temp": None,
                "shaker_active": None,
                "heater_active": None,
            }
            logger.debug(
                f"device unknown and busy. state = {cached_states[stack_floor]}"
            )
        else:
            # query device for state information and save to cached states
            cached_states[stack_floor] = {
                "target_temp": device.get_target_temperature(stack_floor=stack_floor),
                "actual_temp": device.get_actual_temperature(stack_floor=stack_floor),
                "shaker_active": device.is_shaker_active(stack_floor=stack_floor),
                "heater_active": device.is_heater_active(stack_floor=stack_floor),
            }
            logger.debug(
                f"device unknown, not busy. state = {cached_states[stack_floor]}"
            )
    return cached_states[stack_floor]


# DOOR ACTIONS
@app.get("/open_door", summary="opens the incubator door at specified stack_floor")
def open_door(stack_floor: int = Query(..., description="Stack floor number")):
    """Opens the door"""
    device.open_door(stack_floor=stack_floor)
    logger.info(f"door opened @ stack floor {stack_floor}")


@app.get("/close_door", summary="closes the incubator door at specified stack_floor")
def close_door(stack_floor: int = Query(..., description="Stack floor number")):
    """Closes the door"""
    device.close_door(stack_floor=stack_floor)
    logger.info(f"door closed @ stack floor {stack_floor}")


@app.get(
    "/report_door_status",
    summary="reports door status at specified stack floor, 0 closed, 1 open",
)
def report_door_status(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> str:
    """Reports the door status"""
    door_status = device.report_door_status(stack_floor=stack_floor)
    logger.info(f"door status @ stack floor {stack_floor}: {door_status}")
    return door_status


@app.get(
    "/report_labware", summary="reports labware presence at specified stack floor."
)
def report_labware(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> str:
    """Reports the labware status
    Responses:
        0 = no labware present
        1 = labware detected,
        8 = error, door open
        7 = error, reset and door closed
    """
    labware_status = device.report_door_status(stack_floor=stack_floor)
    logger.info(f"report labware @ stack floor {stack_floor}: {labware_status}")
    return labware_status


# TEMPERATURE ACTIONS
@app.get(
    "/get_actual_temperature",
    summary="returns the actual temperature of the incubator at the specified stack floor",
)
def get_actual_temperature(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> float:
    """Returns actual temperature"""
    temperature = device.get_actual_temperature(stack_floor=stack_floor)
    logger.info(f"actual temperature @ stack floor {stack_floor}: {temperature}")
    return temperature


@app.get(
    "/get_target_temperature",
    summary="returns the target temperature of the incubator at the specified stack floor",
)
def get_target_temperature(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> float:
    """Returns target temperature"""
    temperature = device.get_target_temperature(stack_floor=stack_floor)
    logger.info(f"target temperature @ stack floor {stack_floor}: {temperature}")
    return temperature


@app.post(
    "/set_target_temperature",
    summary="Sets the target temperature of the incubator at the specified stack floor",
)
def set_target_temperature(request: TemperatureRequest):
    """Sets the target temperature"""
    device.set_target_temperature(
        stack_floor=request.stack_floor, temperature=request.temperature
    )
    logger.info(
        f"temperature set @ stack floor {request.stack_floor}: {request.temperature}"
    )


# HEATER ACTIONS
@app.get(
    "/start_heater",
    summary="turns on the incubator heater at the specified stack floor",
)
def start_heater(stack_floor: int = Query(..., description="Stack floor number")):
    """Starts the heater"""
    device.start_heater(stack_floor=stack_floor)
    logger.info(f"heater started @ stack floor {stack_floor}")


@app.get(
    "/stop_heater",
    summary="turns off the incubator heater at the specified stack floor",
)
def stop_heater(stack_floor: int = Query(..., description="Stack floor number")):
    """Stops the heater"""
    device.stop_heater(stack_floor=stack_floor)
    logger.info(f"heater stopped @ stack floor {stack_floor}")


@app.get(
    "/is_heater_active",
    summary="turns off the incubator heater at the specified stack floor",
)
def is_heater_active(
    stack_floor: int = Query(..., description="Stack floor number"),
) -> bool:
    """Returns True if heater/cooler is activated, otherwise False"""
    response = device.is_heater_active(stack_floor=stack_floor)
    logger.info(f"heater status @ stack floor {stack_floor}: {response}")
    return response


# SHAKER COMMANDS
@app.post("/start_shaker", summary="starts shaker at the specified stack floor")
def start_shaker(request: StartShakerRequest):
    """Starts the heater"""
    device.start_shaker(stack_floor=request.stack_floor, status=request.status)
    logger.info(f"shaker started @ stack floor {request.stack_floor}")


@app.get("/stop_shaker", summary="stops shaker at the specified stack floor")
def stop_shaker(stack_floor: int = Query(..., description="Stack floor number")):
    """Stops the shaker"""
    device.stop_shaker(stack_floor=stack_floor)
    logger.info(f"shaker stopped @ stack floor {stack_floor}")


@app.get(
    "/is_shaker_active",
    summary="Determines if shaker is active at specified stack floor (True = active, False = inactive).",
)
def is_shaker_active(stack_floor: int = Query(..., description="Stack floor number")):
    """Determines if shaker is active"""
    response = device.is_shaker_active(stack_floor=stack_floor)
    logger.info(f"shaker status @ stack floor {stack_floor}: {response}")
    return response


@app.post(
    "/set_shaker_parameters",
    summary="Sets the shaker parameters at the specified stack floor",
)
def set_shaker_parameters(request: SetShakerParametersRequest):
    """Sets the shaker parameters"""
    device.set_shaker_parameters(
        stack_floor=request.stack_floor, frequency=request.frequency
    )
    logger.info(
        f"shaker parameters set @ stack floor {request.stack_floor}: frequency = {request.frequency}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="host computer IP for the interface API",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="COM5",
        help="COM Port for the incubator device(s)",
    )
    parser.add_argument("--port", type=int, default=7000, help="Port to run FastAPI on")
    parser.add_argument(
        "--dll_path",
        type=str,
        help="Path to inheco device dll",
        default="C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
    )

    args = parser.parse_args()

    app = create_app(device=args.device, dll_path=args.dll_path)
    uvicorn.run(app, host=args.host, port=args.port)
