"""
REST-based node for Inheco Single Plate Incubators that interfaces with WEI
"""

import logging
import time
import traceback
from threading import Thread

import requests
from starlette.datastructures import State
from typing_extensions import Annotated
from wei.modules.rest_module import RESTModule
from wei.types.module_types import (
    ModuleState,
)
from wei.types.step_types import (
    ActionRequest,
    StepResponse,
)

from pydantic_models import (
    SetShakerParametersRequest,
    StartShakerRequest,
    TemperatureRequest,
)

# create logger
logger = logging.getLogger(__name__)

# create rest module
rest_module = RESTModule(
    name="inheco_incubator_module",
    version="0.0.1",
    description="A REST node to control Inheco Single Plate Incubators",
    model="inheco",
)

rest_module.arg_parser.add_argument(
    "--device_id",
    type=int,
    help="device ID of the Inheco Incubator device ",
    default=2,
)
rest_module.arg_parser.add_argument(
    "--stack_floor",
    type=int,
    help="stack floor of the Inheco Incubator device",
    default=0,
)
rest_module.arg_parser.add_argument(
    "--interface_host",
    type=str,
    help="Inheco Interface FastAPI server host",
    default="127.0.0.0",
)
rest_module.arg_parser.add_argument(
    "--interface_port",
    type=int,
    help="Inheco Interface FastAPI server port",
    default=7000,
)

# parse the arguments
args = rest_module.arg_parser.parse_args()

# format logging file based on device id
logging.basicConfig(
    filename=f"inheco_deviceID{args.device_id}_stackFloor{args.stack_floor}.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@rest_module.startup()
def inheco_startup(state: State):
    """Initializes the inheco interface and opens the COM connection"""
    state.is_incubating_only = False
    state.incubation_seconds_remaining = 0
    state.stack_floor = args.stack_floor

    logger.info("startup called")

    # configure urls for connection to Interface API
    state.base_url = f"http://{args.interface_host}:{args.interface_port}"

    # initialize device
    response = send_get_request(
        base_url=state.base_url,
        action_string="initialize",
        stack_floor=state.stack_floor,
    )

    # log
    logger.debug(response)
    logger.info("startup complete")


# HELPER FUNCTIONS
def reset_device(state: State):  # for admin actions
    """Resets the device
    TODO: return step succeded?
    """
    logger.info("restart called")
    response = send_get_request(
        base_url=state.base_url,
        action_string="reset",
        stack_floor=state.stack_floor,
    )
    logger.debug(response)
    logger.info("restart complete")


def send_get_request(base_url, action_string: str, stack_floor: int):
    "Sends http get requests"
    response = None
    try:
        endpoint = f"/{action_string}?stack_floor={stack_floor}"
        request_url = f"{base_url}{endpoint}"
        response = requests.get(request_url)
        response.raise_for_status()
    except Exception as e:
        raise e
    return response


def send_post_request(base_url, action_string, arguments_dict=None):
    "Sends http post requests"
    response = None
    try:
        endpoint = f"/{action_string}"
        request_url = f"{base_url}{endpoint}"
        response = requests.post(request_url, json=arguments_dict)
        response.raise_for_status()
    except Exception as e:
        raise e
    return response


def count_down_incubation(state: State, total_incubation_seconds: int):
    """Counts down the incubation time and updates state"""
    incubation_seconds_completed = 0

    # count down incubation seconds and update state
    logger.info(f"Starting incubation for {total_incubation_seconds} seconds")
    while int(incubation_seconds_completed) < int(total_incubation_seconds):
        time.sleep(1)
        incubation_seconds_completed += 1
        state.incubation_seconds_remaining = (
            total_incubation_seconds - incubation_seconds_completed
        )
    logger.info("Incubation complete")

    # reset the incubation_time_remaining variable for next actions
    state.incubation_seconds_remaining = 0

    # stop shaking after completed incubation
    send_get_request(state.base_url, "stop_shaker", stack_floor=state.stack_floor)
    logger.info("Shaker stopped after incubation")


class IncubateParametersError(Exception):
    """raised when incubation action parameters are invalid"""

    pass


# CUSTOM STATE HANDLER
@rest_module.state_handler()
def inheco_state_handler(state: State) -> ModuleState:
    """Returns the state of the Inheco device and module"""

    # request state from FastAPI endpoint
    response = send_get_request(
        state.base_url, action_string="get_state", stack_floor=state.stack_floor
    )
    response.raise_for_status()
    device_state = response.json()

    if device_state:
        return ModuleState.model_validate(
            {
                "status": state.status,
                "error": state.error,
                "target_temp": device_state["target_temp"],
                "actual_temp": device_state["actual_temp"],
                "shaker_active": device_state["shaker_active"],
                "heater_active": device_state["heater_active"],
                "incubation_seconds_remaining": state.incubation_seconds_remaining,
            }
        )
    else:
        logger.debug(
            f"Unable to collect device state at stack floor {state.stack_floor}"
        )
        return ModuleState.model_validate(
            {
                "status": state.status,
                "error": state.error,
                "incubation_seconds_remaining": state.incubation_seconds_remaining,
            }
        )


# OPEN TRAY ACTION
@rest_module.action(name="open", description="Open the plate tray")
def open(
    state: State,
    action: ActionRequest,
) -> StepResponse:
    """Opens the Inheco incubator tray"""
    logger.info("open called")

    response = send_get_request(
        state.base_url, action_string="open_door", stack_floor=state.stack_floor
    )

    logger.debug(response)
    logger.info("open complete")

    return StepResponse.step_succeeded()


# CLOSE TRAY ACTION
@rest_module.action(name="close", description="Close the plate tray")
def close(
    state: State,
    action: ActionRequest,
) -> StepResponse:
    """Closes the Tekmatic incubator tray"""
    logger.info("close called")
    response = send_get_request(
        state.base_url, action_string="close_door", stack_floor=state.stack_floor
    )
    logger.debug(response)
    logger.info("close complete")

    return StepResponse.step_succeeded()


# SET TEMPERATURE ACTION
@rest_module.action(
    name="set_temperature", description="Set target incubation temperature"
)
def set_temperature(
    state: State,
    action: ActionRequest,
    temperature: Annotated[
        float,
        "temperature in Celsius to one decimal point. 0.0 - 80.0 are valid inputs, 22.0 default",
    ] = 22.0,
    activate: Annotated[
        bool,
        "(optional) turn on heating/cooling element, on = True (default), off = False",
    ] = False,
) -> StepResponse:
    """Sets the temperature in Celsius on the Tekmatic incubator. If activate is set to False, heating element will turn off"""
    logger.info("set temperature called")

    # set the target temperature
    try:
        payload = TemperatureRequest(
            stack_floor=state.stack_floor, temperature=temperature
        )
        payload_dict = payload.model_dump()
        response = send_post_request(
            state.base_url, "set_target_temperature", arguments_dict=payload_dict
        )
        print(response)
    except Exception as e:
        return StepResponse.step_failed(error=str(e))

    # turn on/off the heater
    # NOTE: there is a bug in the WEI dashboard, activate is passed in as string, not boolean, thus "false"(str) => True(bool)
    try:
        if activate:
            response = send_get_request(
                state.base_url, "start_heater", stack_floor=state.stack_floor
            )
        else:
            response = send_get_request(
                state.base_url, "stop_heater", stack_floor=state.stack_floor
            )
    except Exception as e:
        return StepResponse.step_failed(error=str(e))
    return StepResponse.step_succeeded()


# INCUBATE ACTION
@rest_module.action(
    name="incubate", description="Start incubation with optional shaking"
)
def incubate(
    state: State,
    action: ActionRequest,
    temperature: Annotated[
        float,
        "temperature in celsius to one decimal point. 0.0 - 80.0 are valid inputs, 22.0 default",
    ] = 22.0,
    shaker_frequency: Annotated[
        float,
        "shaker frequency in Hz (1Hz = 60rpm). 0 (no shaking) and 6.6-30.0 are valid inputs, default is 14.2 Hz",
    ] = 14.2,
    wait_for_incubation_time: Annotated[
        bool,
        "True if action should block until the specified incubation time has passed, False to continue immediately after starting the incubation",
    ] = False,
    incubation_time: Annotated[int, "Time to incubate in seconds"] = None,
) -> StepResponse:
    """Starts incubation at the specified temperature, optionally shakes, and optionally blocks all other actions until incubation complete"""

    logger.info("incubate called")

    # set temperature
    try:
        # set temperature parameters
        payload = TemperatureRequest(
            stack_floor=state.stack_floor, temperature=temperature
        )
        payload_dict = payload.model_dump()
        send_post_request(
            state.base_url, "set_target_temperature", arguments_dict=payload_dict
        )

        # start the heater
        send_get_request(state.base_url, "start_heater", stack_floor=state.stack_floor)

        logger.info("heater set and started")

    except Exception as e:
        logger.error(f"Error starting heater in incubate action: {e}")
        logger.error(traceback.format_exc())
        print(f"Error starting heater in incubate action: {e}")
        return StepResponse.step_failed(
            error="Failed to set temperature in incubate action"
        )

    # set shaker
    try:
        if (
            not shaker_frequency == 0
        ):  # don't start the shaker if user sets shaker frequency to 0
            # set the shaker parameters
            payload = SetShakerParametersRequest(
                stack_floor=state.stack_floor, frequency=shaker_frequency
            )
            payload_dict = payload.model_dump()
            send_post_request(
                state.base_url, "set_shaker_parameters", arguments_dict=payload_dict
            )

            # start shaker (status = "ND" means shake without checking for labware)
            payload = StartShakerRequest(stack_floor=state.stack_floor, status="ND")
            payload_dict = payload.model_dump()
            send_post_request(
                base_url=state.base_url,
                action_string="start_shaker",
                arguments_dict=payload_dict,
            )
            logger.info("shaker set and started")

    except Exception as e:
        logger.error(f"Error starting shaker in incubate action: {e}")
        logger.error(traceback.format_exc())
        print(f"Error starting shaker in incubate action: {e}")
        return StepResponse.step_failed(
            error=f"Failed to set shaker parameters or start shaking in incubate action: {traceback.format_exc()}"
        )

    # incubate
    try:
        if wait_for_incubation_time:
            if incubation_time:
                # call countdown incubation time in SAME process
                count_down_incubation(
                    state=state, total_incubation_seconds=incubation_time
                )
            else:
                raise IncubateParametersError(
                    "You must specify incubation_time if wait_for_incubation is True"
                )
        else:
            if incubation_time:
                # call countdown incubation time in DIFFERENT process
                thread = Thread(
                    target=count_down_incubation,
                    args=(state, incubation_time),
                    daemon=True,
                )
                thread.start()
            else:
                # return success immediately, user can heat and shake indefinitely
                pass
        return StepResponse.step_succeeded()

    except Exception as e:
        logger.error("Error starting incubation")
        logger.debug(traceback.format_exc())
        return StepResponse.step_failed(f"Error starting incubation: {e}")


# ****************#
# *Admin Commands*#
# ****************#

"""
To add support for custom admin actions, uncomment one or more of the
functions below.
By default, a module supports SHUTDOWN, RESET, LOCK, and UNLOCK modules. This can be overridden by using the decorators below, or setting a custom Set for python_rest_module.admin_commands
"""

# @rest_module.pause    # TODO: implement
# def pause(state: State):
#     """Support pausing actions on this module"""
#     pass

# @rest_module.resume    # TODO: implement
# def resume(state: State):
#     """Support resuming actions on this module"""
#     pass

# @rest_module.cancel   # TODO: implement
# def cancel(state: State):
#     """Support cancelling actions on this module"""
#     pass

# @rest_module.reset    # TODO: implement
# def reset(state: State):
#     """Support resetting the module.
#     This should clear errors and reconnect to/reinitialize the device, if possible"""
#     state.tekmatic.reset_device()
#     state.tekmatic.initialize()

# default LOCK and UNLOCK actions are sufficient


# *This runs the arg_parser, startup lifecycle method, and starts the REST server
if __name__ == "__main__":
    rest_module.start()
