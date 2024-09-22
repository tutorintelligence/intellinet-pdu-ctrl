from intellinet_pdu_ctrl.api import IPU, OutletCommand

if __name__ == "__main__":
    ipu = IPU("192.168.194.23:50071")
    print(ipu.get_status())

    ipu.set_outlets_state(OutletCommand.POWER_CYCLE_OFF_ON, 3)

    for i in range(100000):
        print(f"{i}: {ipu.get_status().outlet_states[3]}")
