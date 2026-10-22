# TODO: Not integrated into RASER; replace hard-coded study values with an explicit tested contract.


def main():
    eV = 1.6e-19
    proton_fluence = 2e15 * 5 * 1e-3 * 5 * 1e-3
    single_energy = 0.04311 * 1e6 * eV
    total_energy = single_energy * proton_fluence

    print("thermal energy per second = " + str(total_energy) + " J")

    thickness = 500 * 1e-6
    thermal_conductivity = 6.3
    T = total_energy / thermal_conductivity / thickness

    print("delat_T =" + str(T) + " K")


if __name__ == "__main__":
    main()
