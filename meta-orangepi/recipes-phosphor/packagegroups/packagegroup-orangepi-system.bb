SUMMARY = "Orange Pi Zero 2 OpenBMC system management"
DESCRIPTION = "Generic OpenBMC state and inventory management for the Orange Pi BMC."
LICENSE = "Apache-2.0"

inherit packagegroup

# A board without a host power controller still needs a real provider for the
# full image's system-management feature.  The standard state/inventory
# managers are the platform-neutral OpenBMC implementation.
RPROVIDES:${PN} = "virtual-obmc-system-mgmt"
RDEPENDS:${PN} = " \
    phosphor-state-manager-bmc \
    phosphor-state-manager-chassis \
    phosphor-state-manager-host \
    phosphor-inventory-manager \
    "
