"""
REST-based node for Inheco Single Plate Incubators that interfaces with MADSci
"""

import threading
import time
import traceback
from threading import Thread
from typing import Annotated, Optional

import requests
from madsci.common.types.action_types import ActionCancelled, ActionFailed
from madsci.common.types.admin_command_types import AdminCommandResponse
from madsci.common.types.node_types import RestNodeConfig
from madsci.common.types.resource_types import (
    Slot,
)
from madsci.node_module.helpers import action
from madsci.node_module.rest_node_module import RestNode

from pydantic_models import (
    SetShakerParametersRequest,
    StartShakerRequest,
    TemperatureRequest,
)

"""
TODO:
- Add admin actions
    Bug: Dashboard buttons not registering when admin action is available
    Bug: Shutdown module admin action throws error in module
- add back in logging files separated by device
- add back in state and error flags in state function
- Do I need a custom shutdown handler? if not, delete the function
- Check if this bug still exists in MADSci when setting temperature through dashboard
    # NOTE: there is a bug in the dashboard, activate is passed in as string, not boolean, thus "false"(str) => True(bool)
- Do I need self.cancelled in the startup handler?
- pass all pre-commit checks
- Test to make sure all cleanup changes still work
- Should I be validating inputs with my pydantic models?
"""


class InhecoNodeConfig(RestNodeConfig):
    """Configuration for the Inheco Node"""

    device_id: int = 2
    """device ID of the Inheco Incubator device"""
    stack_floor: int = 0
    """stack floor of the Inheco Incubator device"""
    interface_host: str = "127.0.0.1"
    """Inheco Interface FastAPI server host"""
    interface_port: int = 7000
    """Inheco Interface FastAPI server port"""
    state_update_interval: Optional[float] = 5.0
    """Interval for updating module state in seconds"""


class InhecoNode(RestNode):
    """A node to control the Inheco incubator device"""

    config_model = InhecoNodeConfig
    config: InhecoNodeConfig = InhecoNodeConfig()
    module_version = "1.1.0"

    # LIFECYCLE AND RESOURCE FUNCTIONS
    def startup_handler(self) -> None:
        """Called to (re)initialize the node. Should be used to open connections to devices or initialize any other resources."""

        self.init_resource_templates()
        self.create_resources()

        self.is_incubating_only = False
        self.incubation_seconds_remaining = 0
        self.end_incubation_time = None
        self.incubate_thread = None
        # self.cancelled = False
        self.stop_incubation_event = threading.Event()

        self.logger.log_info("startup called")

        # configure urls for connection to Interface API
        self.base_url = (
            f"http://{self.config.interface_host}:{self.config.interface_port}"
        )

        # initialize device
        response = self.send_get_request(
            action_string="initialize",
        )

        # log
        self.logger.log_debug(response)
        self.logger.log_info("startup complete")

    def init_resource_templates(self) -> None:
        """Initialize resource templates for the node module."""

        self.resource_client.create_template(
            resource=Slot(
                resource_description="The plate nest for an Inheco microplate reader",
            ),
            template_name="inheco.nest",
            description="Template of an Inheco microplate reader plate nest",
            tags=["PlateNest", "ANSI/SLAS"],
        )

    def create_resources(self) -> None:
        """Create resources for the node module."""

        self.plate_carrier = self.resource_client.create_resource_from_template(
            template_name="inheco.nest",
            resource_name=f"{self.node_definition.node_name}.nest",
        )

    # CUSTOM STATE HANDLER
    def state_handler(self) -> None:
        """Periodically checks the state of the Inheco device and module"""
        
        try: 
            # request state from FastAPI endpoint
            response = self.send_get_request(action_string="get_state")
            response.raise_for_status()
            device_state = response.json()
            if device_state:
                self.node_state = {
                    "target_temp": device_state["target_temp"],
                    "actual_temp": device_state["actual_temp"],
                    "shaker_active": device_state["shaker_active"],
                    "heater_active": device_state["heater_active"],
                    "incubation_seconds_remaining": self.incubation_seconds_remaining,
                }
            else:
                self.logger.log_debug(
                    f"Unable to collect device state at stack floor {self.config.stack_floor}"
                )
                self.node_state = {
                    "incubation_seconds_remaining": self.incubation_seconds_remaining,
                }
        
        except Exception as e: 
            self.logger.log_error(f"Error collecting state information in state handler: {e}")

    def shutdown_handler(self) -> None:  # TODO: default is probably sufficient
        """Handles node shutdown procedure"""
        # TODO: cancel any running incubation thread?
        return super().shutdown_handler()

    # HELPER FUNCTIONS
    def send_get_request(self, action_string: str) -> requests.Response:
        """Sends http get requests"""
        response = None
        try:
            endpoint = f"/{action_string}?stack_floor={self.config.stack_floor}"
            request_url = f"{self.base_url}{endpoint}"
            response = requests.get(request_url)
            response.raise_for_status()
        except Exception as e:
            raise e
        return response

    def send_post_request(
        self, action_string: str, arguments_dict=None
    ) -> requests.Response:
        "Sends http post requests"
        response = None
        try:
            endpoint = f"/{action_string}"
            request_url = f"{self.base_url}{endpoint}"
            response = requests.post(request_url, json=arguments_dict)
            response.raise_for_status()
        except Exception as e:
            raise e
        return response

    def count_down_incubation(
        self, total_incubation_seconds: int
    ) -> ActionCancelled | None:
        """Counts down the incubation time and updates state"""

        # count down incubation seconds and update state
        self.logger.log_info(
            f"Starting incubation for {total_incubation_seconds} seconds"
        )

        # set up incubation variables
        elapsed = 0
        check_interval = 1  # check every second
        start_incubation_time = time.time()
        self.end_incubation_time = start_incubation_time + total_incubation_seconds

        while time.time() < self.end_incubation_time:
            # check if we should stop
            if self.cancelled:
                # reset canceled
                self.cancelled = False
                return ActionCancelled()

            time.sleep(check_interval)

            elapsed += check_interval
            self.incubation_seconds_remaining = total_incubation_seconds - elapsed

        self.logger.log_info("Incubation complete")

        # reset the incubation_time_remaining variable for next actions
        self.incubation_seconds_remaining = 0

        # stop shaking after completed incubation
        self.send_get_request(action_string="stop_shaker")
        self.logger.log_info("Shaker stopped after incubation")

        return None  # TODO: check that this is fine

    # MODULE ACTIONS
    # Open tray
    @action(name="open")
    def open(self) -> None:
        """Opens the Inheco incubator tray"""
        self.logger.log_info("open called")

        # stop the shaker if running
        response = self.send_get_request(action_string="stop_shaker")
        self.logger.log_debug("stopping shaker")
        self.logger.log_debug(response)

        # open the door
        response = self.send_get_request(action_string="open_door")
        self.logger.log_debug(response)
        self.logger.log_info("open complete")

    # Close tray
    @action(name="close")
    def close(self) -> None:
        """Closes the Inheco incubator tray"""
        self.logger.log_info("close called")
        response = self.send_get_request(action_string="close_door")
        self.logger.log_debug(response)
        self.logger.log_info("close complete")

    # Set temperature
    @action(name="set_temperature")
    def set_temperature(
        self,
        temperature: Annotated[
            Optional[float],
            "temperature in Celsius to one decimal point. 0.0 - 80.0 are valid inputs, 22.0 default",
        ] = 22.0,
        activate: Annotated[
            Optional[bool],
            "(optional) turn on heating/cooling element, on = True (default), off = False",
        ] = False,
    ) -> None:
        """Sets the temperature in Celsius on the Inheco incubator. If activate is set to False, heating element will turn off"""
        self.logger.log_info("set temperature called")

        # Set the target temperature
        try:
            payload = TemperatureRequest(
                stack_floor=self.config.stack_floor, temperature=temperature
            )
            payload_dict = payload.model_dump()
            response = self.send_post_request(
                action_string="set_target_temperature",
                arguments_dict=payload_dict,
            )
            self.logger.log_debug(response)
        except Exception as e:
            return ActionFailed(errors=[f"Error setting target temperature: {e}"])

        # Turn on/off the heater
        try:
            if activate:
                response = self.send_get_request(action_string="start_heater")
            else:
                response = self.send_get_request(action_string="stop_heater")
        except Exception as e:
            return ActionFailed(errors=[f"Error setting heater: {e}"])

    # Incubate
    @action(name="incubate")
    def incubate(
        self,
        temperature: Annotated[
            Optional[float],
            "temperature in celsius to one decimal point. 0.0 - 80.0 are valid inputs, 22.0 default",
        ] = 22.0,
        shaker_frequency: Annotated[
            Optional[float],
            "shaker frequency in Hz (1Hz = 60rpm). 0 (no shaking) and 6.6-30.0 are valid inputs, default is 14.2 Hz",
        ] = 14.2,
        wait_for_incubation_time: Annotated[
            Optional[bool],
            "True if action should block until the specified incubation time has passed, False to continue immediately after starting the incubation",
        ] = False,
        incubation_time: Annotated[Optional[int], "Time to incubate in seconds"] = None,
    ) -> None:
        """Starts incubation at the specified temperature, optionally shakes, and optionally blocks all other actions until incubation complete"""

        self.logger.log_info("incubate called")
        self.cancelled = False

        # set temperature
        try:
            # set temperature parameters
            payload = TemperatureRequest(
                stack_floor=self.config.stack_floor, temperature=temperature
            )
            payload_dict = payload.model_dump()
            self.send_post_request(
                action_string="set_target_temperature", arguments_dict=payload_dict
            )

            # start the heater
            self.send_get_request("start_heater")
            self.logger.log_info("heater set and started")

        except Exception as e:
            self.logger.log_error(f"Error starting heater in incubate action: {e}")
            self.logger.log_error(traceback.format_exc())
            return ActionFailed(errors=[f"Failed to set temperature action: {e}"])

        # set shaker
        try:
            # don't start the shaker if user sets shaker frequency to 0
            if shaker_frequency != 0:
                # set the shaker parameters
                payload = SetShakerParametersRequest(
                    stack_floor=self.config.stack_floor, frequency=shaker_frequency
                )
                payload_dict = payload.model_dump()
                self.send_post_request(
                    action_string="set_shaker_parameters",
                    arguments_dict=payload_dict,
                )

                # start shaker (status = "ND" means shake without checking for labware)
                payload = StartShakerRequest(
                    stack_floor=self.config.stack_floor, status="ND"
                )
                payload_dict = payload.model_dump()
                self.send_post_request(
                    action_string="start_shaker",
                    arguments_dict=payload_dict,
                )
                self.logger.log_info("shaker set and started")

        except Exception as e:
            self.logger.log_error(f"Error starting shaker in incubate action: {e}")
            self.logger.log_error(traceback.format_exc())
            return ActionFailed(
                errors=[
                    f"Failed to set shaker parameters or start shaking in incubate action: {traceback.format_exc()}"
                ]
            )

        # optionally wait for incubation time
        try:
            if wait_for_incubation_time:
                if incubation_time:
                    # call countdown incubation time in SAME process
                    return self.count_down_incubation(
                        total_incubation_seconds=incubation_time
                    )
                return ActionFailed(
                    errors="You must specify incubation_time if wait_for_incubation is True"
                )
            if incubation_time:
                # call countdown incubation time in DIFFERENT process
                self.incubate_thread = Thread(
                    target=self.count_down_incubation,
                    args=[incubation_time],
                    daemon=True,
                )
                self.incubate_thread.start()

            else:
                # return success immediately, user can heat and shake indefinitely
                pass

        except Exception as e:
            self.logger.log_error("Error starting incubation")
            self.logger.log_debug(traceback.format_exc())
            return ActionFailed(errors=[f"Error starting incubation: {e}"])

    # ADMIN ACTIONS
    def reset(self) -> AdminCommandResponse:
        """Resets the inheco incubator node"""

        try:
            # cancel any running incubation
            self.cancel()

            # turn heater off if running
            if self.node_state["heater_active"] == "true":
                response = self.send_get_request(action_string="stop_heater")
                self.logger.log_debug("stopping heater")
                self.logger.log_debug(response)
            else:
                self.logger.log("Heater not active, no need to deactivate it")

            return super().reset()

        except Exception as e:
            self.logger.log_error(f"Error resetting node: {e}")
            return AdminCommandResponse(success=False, errors=[e])

    def cancel(self) -> AdminCommandResponse:
        """Cancels the current action, probably incubation"""

        try:
            # Cancel the incubation countdown
            self.cancelled = True

            self.end_incubation_time = time.time()
            self.incubation_seconds_remaining = 0

            # return that admin command executed successfully
            return AdminCommandResponse(success=True)

        except Exception as e:
            self.logger.log_error(f"Error from cancel admin action: {e}")
            return AdminCommandResponse(success=False, errors=[e])


if __name__ == "__main__":
    inheco_node = InhecoNode()
    inheco_node.start_node()
