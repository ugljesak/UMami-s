--------------------------------------------------------------------------------
--  ps2_mouse.vhd
--
--  PS/2 mouse controller.
--
--  Handles the full device bring-up (reset -> BAT -> enable reporting) and then
--  continuously receives the 3-byte movement packets, presenting them on three
--  8-bit output ports.
--
--  Packet layout (standard PS/2 mouse, stream mode):
--      byte 0  STATUS : bit7 = Y overflow
--                       bit6 = X overflow
--                       bit5 = Y sign  (1 = negative)
--                       bit4 = X sign  (1 = negative)
--                       bit3 = always 1  (used here for packet sync)
--                       bit2 = middle button
--                       bit1 = right button
--                       bit0 = left button
--      byte 1  X_MOV  : low 8 bits of a 9-bit two's complement value,
--                       the 9th (sign) bit is STATUS(4)
--      byte 2  Y_MOV  : low 8 bits of a 9-bit two's complement value,
--                       the 9th (sign) bit is STATUS(5).
--                       Y is positive going UP the screen.
--
--  IMPORTANT - ps2_clk and ps2_data are BIDIRECTIONAL open-collector lines.
--  A mouse does not report anything until the host sends it commands, so this
--  component must be able to drive both lines low.  Connect them to bidir
--  (INOUT) pins and make sure a pull-up is present - most FPGA boards have
--  external 1k-10k pull-ups on the PS/2 connector; if yours does not, enable
--  the weak internal pull-up on those pins in the pin planner.
--
--  Bring-up sequence performed automatically after reset:
--      host -> 0xFF (reset)
--      dev  -> 0xFA (ack), 0xAA (self-test passed), 0x00 (mouse ID)
--      host -> 0xF4 (enable data reporting)
--      dev  -> 0xFA (ack)
--  If any step times out or answers unexpectedly the whole sequence restarts,
--  so unplugging and replugging the mouse recovers by itself.
--------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity ps2_mouse is
    generic (
        -- Frequency of the board clock fed into "clk". Every internal timing
        -- constant is derived from this, so it is the only thing you need to
        -- change when moving to another board.
        CLK_FREQ_HZ : integer := 50_000_000
    );
    port (
        clk        : in    std_logic;                     -- board clock
        reset      : in    std_logic;                     -- synchronous, active HIGH (tie to '0' if unused)

        ps2_clk    : inout std_logic;                     -- PS/2 connector pin 5
        ps2_data   : inout std_logic;                     -- PS/2 connector pin 1

        status     : out   std_logic_vector(7 downto 0);  -- buttons / signs / overflow
        x_mov      : out   std_logic_vector(7 downto 0);  -- X movement
        y_mov      : out   std_logic_vector(7 downto 0);  -- Y movement

        data_valid : out   std_logic;                     -- 1-clk pulse: a new packet was latched
        ready      : out   std_logic                      -- '1' once the mouse is initialised & streaming
    );
end entity ps2_mouse;


architecture rtl of ps2_mouse is

    ----------------------------------------------------------------------------
    -- Timing constants derived from the board clock
    ----------------------------------------------------------------------------
    constant C_100US : integer := CLK_FREQ_HZ / 10_000;      -- clock inhibit time
    constant C_10US  : integer := CLK_FREQ_HZ / 100_000;     -- start-bit setup time
    constant C_POR   : integer := CLK_FREQ_HZ / 20;          --  50 ms power-on / retry delay
    constant C_RXTO  : integer := CLK_FREQ_HZ / 200;         --   5 ms mid-byte watchdog
    constant C_STRTO : integer := CLK_FREQ_HZ / 40;          --  25 ms packet re-sync watchdog
    constant C_CMDTO : integer := (CLK_FREQ_HZ / 4) * 3;     -- 750 ms command response timeout

    ----------------------------------------------------------------------------
    -- Odd parity: returns the bit that makes the total number of ones odd
    ----------------------------------------------------------------------------
    function odd_par (v : std_logic_vector(7 downto 0)) return std_logic is
        variable p : std_logic := '1';
    begin
        for i in v'range loop
            p := p xor v(i);
        end loop;
        return p;
    end function;

    ----------------------------------------------------------------------------
    -- Input synchronisation and glitch filtering
    ----------------------------------------------------------------------------
    signal clk_meta : std_logic_vector(1 downto 0) := (others => '1');
    signal dat_meta : std_logic_vector(1 downto 0) := (others => '1');
    signal clk_hist : std_logic_vector(7 downto 0) := (others => '1');
    signal c_f      : std_logic := '1';   -- filtered ps2_clk
    signal c_f_d    : std_logic := '1';
    signal c_fall   : std_logic;          -- 1-clk pulse on falling edge of ps2_clk
    signal d_f      : std_logic := '1';   -- synchronised ps2_data

    ----------------------------------------------------------------------------
    -- Open-collector drivers ('1' = pull the line low)
    ----------------------------------------------------------------------------
    signal clk_low : std_logic := '0';
    signal dat_low : std_logic := '0';

    ----------------------------------------------------------------------------
    -- Byte receiver
    ----------------------------------------------------------------------------
    signal rx_en   : std_logic := '0';
    signal rx_cnt  : integer range 0 to 10 := 0;
    signal rx_sr   : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_par  : std_logic := '0';
    signal rx_byte : std_logic_vector(7 downto 0) := (others => '0');
    signal rx_done : std_logic := '0';
    signal rx_wd   : integer range 0 to C_RXTO := 0;
    signal rx_to   : std_logic := '0';

    ----------------------------------------------------------------------------
    -- Main state machine
    ----------------------------------------------------------------------------
    type state_t is (S_POR, S_DISPATCH, S_TX_INHIBIT, S_TX_START,
                     S_TX_BITS, S_TX_DONE, S_EXPECT, S_STREAM);

    signal state    : state_t := S_POR;
    signal step     : integer range 0 to 6 := 0;
    signal tmr      : integer range 0 to C_CMDTO := C_POR;
    signal tx_sr    : std_logic_vector(8 downto 0) := (others => '0'); -- 8 data + parity
    signal tx_cnt   : integer range 0 to 10 := 0;
    signal byte_idx : integer range 0 to 2 := 0;
    signal st_r     : std_logic_vector(7 downto 0) := (others => '0');
    signal x_r      : std_logic_vector(7 downto 0) := (others => '0');

begin

    ----------------------------------------------------------------------------
    -- Tri-state (open-collector) bus drivers
    ----------------------------------------------------------------------------
    ps2_clk  <= '0' when clk_low = '1' else 'Z';
    ps2_data <= '0' when dat_low = '1' else 'Z';

    ready    <= '1' when state = S_STREAM else '0';

    ----------------------------------------------------------------------------
    -- Synchronise the PS/2 lines into the board clock domain and filter the
    -- clock line.  The PS/2 clock runs at 10-16.7 kHz, so a filter of 8 board
    -- clock periods removes contact noise without touching real edges.
    ----------------------------------------------------------------------------
    sync_proc : process (clk)
    begin
        if rising_edge(clk) then
            clk_meta <= clk_meta(0) & To_X01(ps2_clk);
            dat_meta <= dat_meta(0) & To_X01(ps2_data);

            clk_hist <= clk_hist(6 downto 0) & clk_meta(1);
            if clk_hist = "00000000" then
                c_f <= '0';
            elsif clk_hist = "11111111" then
                c_f <= '1';
            end if;

            c_f_d <= c_f;
            d_f   <= dat_meta(1);
        end if;
    end process sync_proc;

    c_fall <= c_f_d and (not c_f);

    ----------------------------------------------------------------------------
    -- Byte receiver.  Device-to-host frame: start(0), 8 data LSB first,
    -- odd parity, stop(1).  Data is valid on the falling edge of ps2_clk.
    -- Disabled (rx_en = '0') while the host is transmitting.
    ----------------------------------------------------------------------------
    rx_proc : process (clk)
    begin
        if rising_edge(clk) then
            rx_done <= '0';
            rx_to   <= '0';

            if reset = '1' or rx_en = '0' then
                rx_cnt <= 0;
                rx_wd  <= 0;

            elsif c_fall = '1' then
                rx_wd <= 0;
                case rx_cnt is

                    when 0 =>                       -- start bit
                        if d_f = '0' then
                            rx_cnt <= 1;
                            rx_par <= '0';
                        end if;

                    when 1 to 8 =>                  -- 8 data bits, LSB first
                        rx_sr  <= d_f & rx_sr(7 downto 1);
                        rx_par <= rx_par xor d_f;
                        rx_cnt <= rx_cnt + 1;

                    when 9 =>                       -- parity bit
                        rx_par <= rx_par xor d_f;
                        rx_cnt <= 10;

                    when others =>                  -- stop bit
                        if d_f = '1' and rx_par = '1' then
                            rx_byte <= rx_sr;       -- stop bit and odd parity OK
                            rx_done <= '1';
                        end if;
                        rx_cnt <= 0;

                end case;

            else
                -- Watchdog: a frame that stalls part way through is abandoned
                if rx_cnt /= 0 then
                    if rx_wd = C_RXTO then
                        rx_wd  <= 0;
                        rx_cnt <= 0;
                        rx_to  <= '1';
                    else
                        rx_wd <= rx_wd + 1;
                    end if;
                else
                    rx_wd <= 0;
                end if;
            end if;
        end if;
    end process rx_proc;

    ----------------------------------------------------------------------------
    -- Main FSM: initialisation sequence, host transmitter, packet assembly
    ----------------------------------------------------------------------------
    main_proc : process (clk)
    begin
        if rising_edge(clk) then
            data_valid <= '0';

            if reset = '1' then
                state    <= S_POR;
                step     <= 0;
                tmr      <= C_POR;
                rx_en    <= '0';
                clk_low  <= '0';
                dat_low  <= '0';
                byte_idx <= 0;
                status   <= (others => '0');
                x_mov    <= (others => '0');
                y_mov    <= (others => '0');

            else
                case state is

                    ------------------------------------------------------------
                    -- Power-on / retry delay: let go of the bus and wait
                    ------------------------------------------------------------
                    when S_POR =>
                        rx_en   <= '0';
                        clk_low <= '0';
                        dat_low <= '0';
                        if tmr = 0 then
                            step  <= 0;
                            state <= S_DISPATCH;
                        else
                            tmr <= tmr - 1;
                        end if;

                    ------------------------------------------------------------
                    -- Decide what the current step of the sequence needs
                    ------------------------------------------------------------
                    when S_DISPATCH =>
                        case step is
                            when 0 =>                       -- send 0xFF (reset)
                                tx_sr <= odd_par(x"FF") & x"FF";
                                tmr   <= C_100US;
                                state <= S_TX_INHIBIT;

                            when 4 =>                       -- send 0xF4 (enable reporting)
                                tx_sr <= odd_par(x"F4") & x"F4";
                                tmr   <= C_100US;
                                state <= S_TX_INHIBIT;

                            when 6 =>                       -- fully initialised
                                rx_en    <= '1';
                                byte_idx <= 0;
                                tmr      <= C_STRTO;
                                state    <= S_STREAM;

                            when others =>                  -- steps 1,2,3,5: expect a byte
                                rx_en <= '1';
                                tmr   <= C_CMDTO;
                                state <= S_EXPECT;
                        end case;

                    ------------------------------------------------------------
                    -- Host-to-device: hold the clock low for >100 us
                    ------------------------------------------------------------
                    when S_TX_INHIBIT =>
                        rx_en   <= '0';
                        clk_low <= '1';
                        if tmr = 0 then
                            tmr   <= C_10US;
                            state <= S_TX_START;
                        else
                            tmr <= tmr - 1;
                        end if;

                    ------------------------------------------------------------
                    -- Pull data low (request-to-send), then release the clock
                    -- so the device starts generating the 11 clock pulses.
                    ------------------------------------------------------------
                    when S_TX_START =>
                        dat_low <= '1';
                        if tmr = 0 then
                            clk_low <= '0';
                            tx_cnt  <= 0;
                            state   <= S_TX_BITS;
                        else
                            tmr <= tmr - 1;
                        end if;

                    ------------------------------------------------------------
                    -- Shift out 8 data bits + parity on falling edges, release
                    -- the line for the stop bit, then read the device ack bit.
                    ------------------------------------------------------------
                    when S_TX_BITS =>
                        if c_fall = '1' then
                            if tx_cnt < 9 then
                                dat_low <= not tx_sr(0);            -- drive low for a '0'
                                tx_sr   <= '0' & tx_sr(8 downto 1);
                                tx_cnt  <= tx_cnt + 1;
                            elsif tx_cnt = 9 then
                                dat_low <= '0';                     -- stop bit
                                tx_cnt  <= 10;
                            else
                                state <= S_TX_DONE;                 -- ack bit from device
                            end if;
                        end if;

                    ------------------------------------------------------------
                    -- Wait for the bus to go idle again, then move on
                    ------------------------------------------------------------
                    when S_TX_DONE =>
                        dat_low <= '0';
                        if c_f = '1' and d_f = '1' then
                            step  <= step + 1;
                            rx_en <= '1';
                            state <= S_DISPATCH;
                        end if;

                    ------------------------------------------------------------
                    -- Expect a specific response byte, otherwise start over
                    ------------------------------------------------------------
                    when S_EXPECT =>
                        if rx_done = '1' then
                            if (step = 1 and rx_byte = x"FA") or   -- ack of 0xFF
                               (step = 2 and rx_byte = x"AA") or   -- self-test passed
                               (step = 3 and rx_byte = x"00") or   -- mouse ID
                               (step = 5 and rx_byte = x"FA") then -- ack of 0xF4
                                step  <= step + 1;
                                state <= S_DISPATCH;
                            else
                                tmr   <= C_POR;
                                state <= S_POR;
                            end if;
                        elsif tmr = 0 then
                            tmr   <= C_POR;
                            state <= S_POR;
                        else
                            tmr <= tmr - 1;
                        end if;

                    ------------------------------------------------------------
                    -- Streaming: assemble 3-byte packets
                    ------------------------------------------------------------
                    when S_STREAM =>
                        if rx_done = '1' then
                            tmr <= C_STRTO;
                            case byte_idx is

                                when 0 =>
                                    -- bit3 of the status byte is always 1; if it
                                    -- is not, we are out of step - drop the byte
                                    if rx_byte(3) = '1' then
                                        st_r     <= rx_byte;
                                        byte_idx <= 1;
                                    end if;

                                when 1 =>
                                    x_r      <= rx_byte;
                                    byte_idx <= 2;

                                when others =>
                                    status     <= st_r;
                                    x_mov      <= x_r;
                                    y_mov      <= rx_byte;
                                    data_valid <= '1';
                                    byte_idx   <= 0;

                            end case;

                        elsif rx_to = '1' then
                            byte_idx <= 0;              -- aborted frame, re-sync

                        elsif tmr = 0 then
                            byte_idx <= 0;              -- long silence, re-sync
                            tmr      <= C_STRTO;

                        else
                            tmr <= tmr - 1;
                        end if;

                end case;
            end if;
        end if;
    end process main_proc;

end architecture rtl;