-- RegFile32x32.vhd
-- Plain array-based 32x32-bit register file, built as a diagnostic drop-in
-- replacement for 32xREG32_FILE.bdf (same port names/widths) to test whether
-- the mux/decoder-based implementation is the cause of the Analysis &
-- Synthesis hang.
--
-- Behavior: synchronous write (on rising CLK, when LD='1', unless RSD=0),
-- combinational (asynchronous) reads on RS1DO/RS2DO, synchronous reset
-- clears all 32 registers. Register 0 is hardwired to zero (never written,
-- always reads zero) per the RISC-V x0 convention -- if your current
-- implementation does NOT do this, that's a behavioral difference to be
-- aware of, though it doesn't affect the hang test either way.

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity RegFile32x32 is
    port (
        RST   : in  std_logic;
        DI    : in  std_logic_vector(31 downto 0);
        RS1   : in  std_logic_vector(4 downto 0);
        RS2   : in  std_logic_vector(4 downto 0);
        RSD   : in  std_logic_vector(4 downto 0);
        CLK   : in  std_logic;
        LD    : in  std_logic;
        RS1DO : out std_logic_vector(31 downto 0);
        RS2DO : out std_logic_vector(31 downto 0)
    );
end entity RegFile32x32;

architecture rtl of RegFile32x32 is
    type reg_array_t is array (0 to 31) of std_logic_vector(31 downto 0);
    signal regs : reg_array_t := (others => (others => '0'));
begin

    process (CLK)
    begin
        if rising_edge(CLK) then
            if RST = '1' then
                regs <= (others => (others => '0'));
            elsif LD = '1' and RSD /= "00000" then
                regs(to_integer(unsigned(RSD))) <= DI;
            end if;
        end if;
    end process;

    RS1DO <= regs(to_integer(unsigned(RS1)));
    RS2DO <= regs(to_integer(unsigned(RS2)));

end architecture rtl;
