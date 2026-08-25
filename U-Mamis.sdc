create_clock -name CLK -period 20.000 [get_ports CLK]
derive_clock_uncertainty
set_false_path -to [get_ports {hundH[*] tensH[*] unitsH[*]}]