from __future__ import annotations

from cloudshell.cli.service.cli import CLI
from cloudshell.cli.service.session_pool_manager import SessionPoolManager
from cloudshell.shell.core.driver_context import (
    AutoLoadCommandContext,
    AutoLoadDetails,
    InitCommandContext,
    ResourceCommandContext,
)
from cloudshell.shell.core.driver_utils import GlobalLock
from cloudshell.shell.core.orchestration_save_restore import OrchestrationSaveRestore
from cloudshell.shell.core.resource_driver_interface import ResourceDriverInterface
from cloudshell.shell.core.session.cloudshell_session import CloudShellSessionContext
from cloudshell.shell.core.session.logging_session import LoggingSessionContext
from cloudshell.shell.flows.command.basic_flow import RunCommandFlow
from cloudshell.shell.standards.networking.autoload_model import NetworkingResourceModel
from cloudshell.shell.standards.networking.driver_interface import (
    NetworkingResourceDriverInterface,
)
from cloudshell.shell.standards.networking.resource_config import (
    NetworkingResourceConfig,
)
from cloudshell.snmp.snmp_configurator import EnableDisableSnmpConfigurator
from cloudshell.calix.cli.calix_cli_configurator import CalixCliConfigurator
from cloudshell.calix.flows.calix_autoload_flow import CalixSnmpAutoloadFlow
from cloudshell.calix.flows.calix_configuration_flow import CalixConfigurationFlow
from cloudshell.calix.flows.calix_enable_disable_snmp_flow import (
    CalixEnableDisableSnmpFlow
)
from cloudshell.calix.flows.calix_state_flow import CalixStateFlow


class CalixDriver(
    ResourceDriverInterface, NetworkingResourceDriverInterface
):
    SUPPORTED_OS = [r"Calix"]
    SHELL_NAME = "Calix AXOS Router 2G"
    SESSION_POOL_TIMEOUT = 300

    def __init__(self):
        super(CalixDriver, self).__init__()
        self._cli = None

    def initialize(self, context: InitCommandContext):
        api = CloudShellSessionContext(context).get_api()
        resource_config = NetworkingResourceConfig.from_context(context, api)
        session_pool_size = int(resource_config.sessions_concurrency_limit)
        self._cli = CLI(
            SessionPoolManager(max_pool_size=session_pool_size, pool_timeout=100)
        )
        return "Finished initializing"

    def health_check(self, context: ResourceCommandContext) -> bool:
        """Performs device health check."""
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            state_operations = CalixStateFlow(resource_config, cli_configurator, api)
            return state_operations.health_check()

    @GlobalLock.lock
    def get_inventory(self, context: AutoLoadCommandContext) -> AutoLoadDetails:
        """Return device structure with all standard attributes."""
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)

            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )
            enable_disable_snmp_flow = CalixEnableDisableSnmpFlow(
                cli_configurator,
                resource_config.vrf_management_name
            )
            snmp_configurator = EnableDisableSnmpConfigurator.from_config(
                enable_disable_snmp_flow, resource_config, logger
            )

            resource_model = NetworkingResourceModel.from_resource_config(
                resource_config
            )

            autoload_operations = CalixSnmpAutoloadFlow(snmp_configurator)
            logger.info("Autoload started")
            response = autoload_operations.discover(self.SUPPORTED_OS, resource_model)
            logger.info("Autoload completed")
            return response

    def ApplyConnectivityChanges(
            self, context: ResourceCommandContext, request: str
    ) -> str:
        """Create vlan and add or remove it to/from network interface."""
        pass

    def run_custom_command(
            self, context: ResourceCommandContext, custom_command: str
    ) -> str:
        """Send custom command."""
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            send_command_operations = RunCommandFlow(cli_configurator)
            response = send_command_operations.run_custom_command(custom_command)
            return response

    def run_custom_config_command(
            self, context: ResourceCommandContext, custom_command: str
    ) -> str:
        """Send custom command in configuration mode."""
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            send_command_operations = RunCommandFlow(cli_configurator)
            result_str = send_command_operations.run_custom_config_command(
                custom_command
            )
            return result_str

    def save(
            self,
            context: ResourceCommandContext,
            folder_path: str,
            configuration_type: str,
            vrf_management_name: str,
    ) -> str:
        """Save selected file to the provided destination.

        :param context: an object with all Resource Attributes inside
        :param configuration_type: source file, which will be saved
        :param folder_path: destination path where file will be saved
        :param vrf_management_name: VRF management Name
        :return str saved configuration file name
        """
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            if not configuration_type:
                configuration_type = "running"

            if not vrf_management_name:
                vrf_management_name = resource_config.vrf_management_name

            configuration_operations = CalixConfigurationFlow(
                resource_config, cli_configurator
            )
            logger.info("Save started")
            response = configuration_operations.save(
                folder_path=folder_path,
                configuration_type=configuration_type,
                vrf_management_name=vrf_management_name,
            )
            logger.info("Save completed")
            return response

    @GlobalLock.lock
    def restore(
            self,
            context: ResourceCommandContext,
            path: str,
            configuration_type: str,
            restore_method: str,
            vrf_management_name: str,
    ):
        """Restore selected file to the provided destination.

        :param context: an object with all Resource Attributes inside
        :param path: source config file
        :param configuration_type: running or startup configs
        :param restore_method: append or override methods
        :param vrf_management_name: VRF management Name
        """
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            if not configuration_type:
                configuration_type = "running"

            if not restore_method:
                restore_method = "override"

            if not vrf_management_name:
                vrf_management_name = resource_config.vrf_management_name

            configuration_operations = CalixConfigurationFlow(
                resource_config, cli_configurator
            )
            logger.info("Restore started")
            configuration_operations.restore(
                path=path,
                restore_method=restore_method,
                configuration_type=configuration_type,
                vrf_management_name=vrf_management_name,
            )
            logger.info("Restore completed")

    @GlobalLock.lock
    def load_firmware(
            self, context: ResourceCommandContext, path: str, vrf_management_name: str
    ):
        """Upload and updates firmware on the resource.

        :param context: an object with all Resource Attributes inside
        :param path: full path to firmware file, i.e. tftp://10.10.10.1/firmware.tar
        :param vrf_management_name: VRF management Name
        """
        pass

    def orchestration_save(
            self, context: ResourceCommandContext, mode: str, custom_params: str
    ) -> str:
        """Save selected file to the provided destination.

        :param context: an object with all Resource Attributes inside
        :param mode: mode
        :param custom_params: json with custom save parameters
        :return str response: response json
        """
        if not mode:
            mode = "shallow"

        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            configuration_operations = CalixConfigurationFlow(
                resource_config, cli_configurator
            )

            logger.info("Orchestration save started")
            response = configuration_operations.orchestration_save(
                mode=mode, custom_params=custom_params
            )
            response_json = OrchestrationSaveRestore(
                resource_config.name
            ).prepare_orchestration_save_result(response)
            logger.info("Orchestration save completed")
            return response_json

    def orchestration_restore(
            self,
            context: ResourceCommandContext,
            saved_artifact_info: str,
            custom_params: str,
    ):
        """Restore selected file to the provided destination.

        :param context: an object with all Resource Attributes inside
        :param saved_artifact_info: OrchestrationSavedArtifactInfo json
        :param custom_params: json with custom restore parameters
        """
        with LoggingSessionContext(context) as logger:
            api = CloudShellSessionContext(context).get_api()

            resource_config = NetworkingResourceConfig.from_context(context, api)
            cli_configurator = CalixCliConfigurator.from_config(
                resource_config, logger, self._cli
            )

            configuration_operations = CalixConfigurationFlow(
                resource_config, cli_configurator
            )

            logger.info("Orchestration restore started")
            restore_params = OrchestrationSaveRestore(
                resource_config.name
            ).parse_orchestration_save_result(saved_artifact_info, custom_params)
            configuration_operations.restore(**restore_params)
            logger.info("Orchestration restore completed")

    def shutdown(self, context):
        """Shutdown device."""
        pass

    def cleanup(self):
        """Destroy the driver session.

        This function is called everytime a driver instance is destroyed.
        This is a good place to close any open sessions, finish writing to log files
        """
        pass
