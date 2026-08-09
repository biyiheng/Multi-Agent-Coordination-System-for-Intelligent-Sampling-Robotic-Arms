using System.Text.Json;

namespace HardwareDebug
{
    // =========================================================================
    // 坐标系变换工具: 与 RPi 端 vision/calibration.py 保持一致 (跨语言对齐)
    // 验证: 像素 -> 相机系 -> 机器人基座系 的手眼标定链路, 单位 mm
    // =========================================================================
    public static class CoordTransform
    {
        public static double[,] K = new double[3, 3] {
            { 320.0, 0.0, 160.0 },
            { 0.0, 320.0, 120.0 },
            { 0.0, 0.0, 1.0 },
        };
        // 相机 -> 机器人旋转 (settings.yaml grasp.hand_eye_rotation)
        public static double[,] R = new double[3, 3] {
            { 1.0, 0.0, 0.0 },
            { 0.0, -1.0, 0.0 },
            { 0.0, 0.0, -1.0 },
        };
        // 相机 -> 机器人平移 mm
        public static double[] t = new double[] { -100.0, -200.0, 50.0 };

        // 针孔模型: 像素 + 深度 Z -> 相机系 (mm)
        public static double[] PixelToCamera(double u, double v, double z)
        {
            double fx = K[0, 0], fy = K[1, 1], cx = K[0, 2], cy = K[1, 2];
            return new[] { (u - cx) * z / fx, (v - cy) * z / fy, z };
        }

        // 相机系 -> 机器人基座系: robot = R * cam + t
        public static double[] CameraToRobot(double[] cam)
        {
            var res = new double[3];
            for (int i = 0; i < 3; i++)
            {
                double acc = t[i];
                for (int j = 0; j < 3; j++) acc += R[i, j] * cam[j];
                res[i] = acc;
            }
            return res;
        }

        // 完整链路: 像素 + 深度 -> 机器人基座系 (mm)
        public static double[] PixelToRobot(double u, double v, double z)
        {
            return CameraToRobot(PixelToCamera(u, v, z));
        }
    }

    // =========================================================================
    // 工作空间: 原点与手眼参数对齐 (修复: 名义 0..500 与手眼映射负坐标矛盾)
    //   robot = R·cam + t, R=diag(1,-1,-1), t=(-100,-200,50)
    //   相机 FOV 典型范围: cam_x∈[-80,80], cam_y∈[-60,60], cam_z∈[200,400]
    //   映射到机器人系:    x∈[-180,-20],  y∈[-260,-140],  z∈[-350,-150]
    // =========================================================================
    public static class Workspace
    {
        // 与手眼变换导出的可达区间一致
        public static readonly (double Min, double Max) X = (-180.0, -20.0);
        public static readonly (double Min, double Max) Y = (-260.0, -140.0);
        public static readonly (double Min, double Max) Z = (-350.0, -150.0);

        public static bool Contains(double x, double y, double z)
        {
            return x >= X.Min && x <= X.Max
                && y >= Y.Min && y <= Y.Max
                && z >= Z.Min && z <= Z.Max;
        }

        public static bool Contains(double[] p)
            => p is { Length: >= 3 } && Contains(p[0], p[1], p[2]);

        public static string Describe()
            => $"x[{X.Min},{X.Max}] y[{Y.Min},{Y.Max}] z[{Z.Min},{Z.Max}] mm";
    }

    // =========================================================================
    // 日志: 结构化 JSON 输出 (对接监控/后端), 与 RPi 端 JsonFormatter 对齐
    // =========================================================================
    public static class JLog
    {
        public static void Emit(string level, string @event, object payload)
        {
            var entry = new Dictionary<string, object?> {
                ["ts"] = DateTime.UtcNow.ToString("o"),
                ["level"] = level,
                ["event"] = @event,
                ["payload"] = payload,
            };
            Console.WriteLine(JsonSerializer.Serialize(entry));
        }
    }

    // =========================================================================
    // 板卡调试模拟 (STM32): 寄存器读写 / PWM 舵机 / UART 回环 / 心跳
    // =========================================================================
    public class Stm32Board
    {
        private readonly Dictionary<string, uint> _regs = new()
        {
            // RCC / GPIO / TIM 关键寄存器 (位域简化为可读写的数值)
            ["RCC_APB2ENR"] = 0x0000001D, // GPIOA/B/C + AFIO 时钟使能
            ["GPIOA_CRL"]   = 0x33333333,
            ["GPIOA_CRH"]   = 0x44444444,
            ["TIM2_CR1"]    = 0x00000001, // 计数使能
            ["TIM2_PSC"]    = 71,         // 预分频 -> 1MHz
            ["TIM2_ARR"]    = 19999,      // 自动重载 -> 50Hz PWM
        };
        private readonly string _port;
        private int _heartbeat;

        public Stm32Board(string port) { _port = port; }

        public string Port => _port;
        public bool Connected { get; private set; }

        public bool Connect()
        {
            Connected = true;
            JLog.Emit("INFO", "board_connect", new { port = _port, baud = 115200, ok = true });
            return true;
        }

        public uint ReadReg(string name)
        {
            if (!_regs.TryGetValue(name, out var val))
                throw new KeyNotFoundException($"未定义的寄存器: {name}");
            JLog.Emit("DEBUG", "reg_read", new { reg = name, value = $"0x{val:X8}" });
            return val;
        }

        public void WriteReg(string name, uint val)
        {
            _regs[name] = val;
            JLog.Emit("DEBUG", "reg_write", new { reg = name, value = $"0x{val:X8}" });
        }

        // 舵机 PWM: 500us=open, 1800us=close (50Hz)
        public void ServoPwm(ushort channel, ushort pulseUs)
        {
            if (pulseUs < 500 || pulseUs > 2500)
                throw new ArgumentOutOfRangeException(nameof(pulseUs), "PWM 脉宽超出 500-2500us");
            // 写 TIM 比较寄存器
            WriteReg($"TIM_CH{channel}_CCR", (uint)(pulseUs / 20)); // 1MHz 计数 -> us
            JLog.Emit("INFO", "servo_pwm", new { channel, pulseUs, action = pulseUs < 1000 ? "open" : "close" });
        }

        public string UartEcho(string data)
        {
            JLog.Emit("DEBUG", "uart_rx", new { data });
            return data; // 回环测试
        }

        public void HeartbeatTick()
        {
            _heartbeat++;
            if (_heartbeat % 5 == 0)
                JLog.Emit("DEBUG", "heartbeat", new { count = _heartbeat });
        }

        public bool VerifyClockConfig()
        {
            uint enr = ReadReg("RCC_APB2ENR");
            bool ok = (enr & 0x1D) == 0x1D; // GPIOA/B/C + AFIO 使能
            JLog.Emit("INFO", "board_selftest", new { rcc_ok = ok, enr = $"0x{enr:X8}" });
            return ok;
        }
    }

    // =========================================================================
    // OpenMV 模拟: 检测请求 -> JSON 响应 (与 openmv_comm.py / apriltag 对齐)
    // =========================================================================
    public class OpenMvCam
    {
        private readonly Random _rnd = new(42);

        // 返回检测 JSON (blob: 像素 cx,cy,area; 或 apriltag: 相机系 x,y,z mm)
        public string Detect(string type)
        {
            if (type.StartsWith("detect_apriltag"))
            {
                // 相机系 6DOF (mm): 目标在相机前方 z=300mm
                double z = 300.0, x = 60.0, y = 30.0;
                var det = new {
                    success = true,
                    type = "apriltag",
                    data = new {
                        found = true, count = 1,
                        tags = new[] { new {
                            id = 0, cx = 224.0, cy = 152.0,
                            x, y, z, roll = 0.0, pitch = 0.0, yaw = 0.0, confidence = 0.95
                        } }
                    }
                };
                return JsonSerializer.Serialize(det);
            }
            // detect_color: 像素坐标 blob
            var d = new {
                success = true,
                type = "color",
                data = new {
                    found = true,
                    detection = new {
                        color = "red",
                        cx = (double)_rnd.Next(100, 220),
                        cy = (double)_rnd.Next(80, 160),
                        width = 32, height = 32,
                        area = 804.0, // 对应深度300mm 处直径32px
                        confidence = 0.92
                    }
                }
            };
            return JsonSerializer.Serialize(d);
        }
    }

    // =========================================================================
    // 多硬件链路模拟: RPi(上位机) --UART--> STM32(passthrough) --> OpenMV
    // =========================================================================
    public class HardwareChain
    {
        private readonly Stm32Board _stm32;
        private readonly OpenMvCam _openmv;

        public HardwareChain()
        {
            _stm32 = new Stm32Board("/dev/ttyAMA0");
            _openmv = new OpenMvCam();
        }

        public void RunChain()
        {
            JLog.Emit("INFO", "chain_start", new { nodes = new[] { "RPi", "STM32", "OpenMV" } });
            _stm32.Connect();

            // 1) RPi -> STM32 -> OpenMV: 发送检测指令 (passthrough)
            const string cmd = "#vision:detect_apriltag:TAG36H11!";
            JLog.Emit("INFO", "chain_rpi_tx", new { cmd });
            _stm32.UartEcho(cmd); // STM32 桥接转发
            string resp = _openmv.Detect("detect_apriltag");
            JLog.Emit("INFO", "chain_openmv_rx", new { raw = resp });

            // 2) 解析相机系坐标 (mm)
            using var doc = JsonDocument.Parse(resp);
            var tag = doc.RootElement.GetProperty("data").GetProperty("tags")[0];
            double camX = tag.GetProperty("x").GetDouble();
            double camY = tag.GetProperty("y").GetDouble();
            double camZ = tag.GetProperty("z").GetDouble();
            JLog.Emit("INFO", "chain_camera_pose", new { x = camX, y = camY, z = camZ, unit = "mm", frame = "camera" });

            // 3) 手眼标定: 相机系 -> 机器人基座系 (与 Python 修复一致)
            double[] robot = CoordTransform.CameraToRobot(new[] { camX, camY, camZ });
            JLog.Emit("INFO", "chain_robot_pose", new {
                x = Math.Round(robot[0], 3), y = Math.Round(robot[1], 3), z = Math.Round(robot[2], 3),
                unit = "mm", frame = "robot_base"
            });

            // 3.1) 工作空间校验: 原点与手眼参数对齐后, 目标应落在可达区间内
            bool inWs = Workspace.Contains(robot);
            JLog.Emit("INFO", "chain_workspace_check", new {
                bounds = Workspace.Describe(),
                target = new[] { Math.Round(robot[0], 1), Math.Round(robot[1], 1), Math.Round(robot[2], 1) },
                inside = inWs,
            });
            if (!inWs)
                JLog.Emit("WARN", "chain_target_out_of_workspace", new { target = robot });

            // 4) 下发机器人运动指令到 STM32 (关节/末端)
            _stm32.ServoPwm(1, 1500); // 关节 1 -> 1500us
            _stm32.WriteReg("MOTION_TARGET_X", (uint)Math.Round(Math.Abs(robot[0])));
            JLog.Emit("INFO", "chain_motion_cmd", new {
                target = new[] { Math.Round(robot[0], 1), Math.Round(robot[1], 1), Math.Round(robot[2], 1) },
                unit = "mm",
            });

            // 5) STM32 确认
            JLog.Emit("INFO", "chain_stm32_ack", new { ack = true, motion = "approach" });

            // 6) 自检
            bool ok = _stm32.VerifyClockConfig();
            JLog.Emit("INFO", "chain_end", new { selftest = ok, status = "completed" });
        }
    }

    // =========================================================================
    // 板卡调试模式: 寄存器 / PWM / UART 回环 / 心跳
    // =========================================================================
    public static class BoardDebug
    {
        public static void Run()
        {
            JLog.Emit("INFO", "debug_start", new { mode = "board_debug", board = "STM32F103(YH-KSTM32)" });

            var board = new Stm32Board("/dev/serial0");
            board.Connect();

            // 时钟自检
            board.VerifyClockConfig();

            // 寄存器读写
            board.WriteReg("TIM2_ARR", 19999);
            board.ReadReg("TIM2_ARR");

            // PWM 舵机: open / close
            board.ServoPwm(1, 500);   // open
            board.ServoPwm(1, 1800);  // close
            board.ServoPwm(1, 900);   // hold

            // UART 回环
            string echoed = board.UartEcho("#PING!");
            JLog.Emit("INFO", "uart_echo", new { echoed, pass = echoed == "#PING!" });

            // 心跳 (模拟若干拍)
            for (int i = 0; i < 12; i++) board.HeartbeatTick();

            JLog.Emit("INFO", "debug_end", new { status = "completed" });
        }
    }

    // =========================================================================
    // C# 侧单元测试: 坐标变换 + 工作空间边界 (无依赖自测运行器)
    // =========================================================================
    public static class CoordinateTests
    {
        private static int _passed = 0;
        private static int _failed = 0;

        private static void Assert(bool cond, string name, string detail = "")
        {
            if (cond)
            {
                _passed++;
                Console.WriteLine($"[PASS] {name} {detail}");
            }
            else
            {
                _failed++;
                Console.WriteLine($"[FAIL] {name} {detail}");
            }
        }

        private static bool Near(double a, double b, double tol = 1e-6)
            => Math.Abs(a - b) <= tol;

        public static int Run()
        {
            Console.WriteLine("== C# 单元测试: 坐标变换与工作空间 ==");

            // ---- 1. 像素 -> 相机系 (主点边界) ----
            var p0 = CoordTransform.PixelToCamera(160.0, 120.0, 300.0);
            Assert(Near(p0[0], 0) && Near(p0[1], 0) && Near(p0[2], 300),
                "主点处像素映射到相机系原点 (x=y=0,z=300)", $"got=({p0[0]},{p0[1]},{p0[2]})");

            // ---- 2. 像素 -> 相机系 (FOV 内正前方) ----
            var p1 = CoordTransform.PixelToCamera(224.0, 152.0, 300.0);
            Assert(Near(p1[0], 60) && Near(p1[1], 30) && p1[2] > 0,
                "FOV 内像素映射为正前方 (60,30,300)", $"got=({p1[0]:F2},{p1[1]:F2},{p1[2]})");

            // ---- 3. 相机 -> 机器人系 (手眼往返) ----
            var cam = new double[] { 60.0, 30.0, 300.0 };
            var robot = CoordTransform.CameraToRobot(cam);
            // 期望 robot = R·cam + t = (60-100, -30-200, -300+50)
            Assert(Near(robot[0], -40) && Near(robot[1], -230) && Near(robot[2], -250),
                "手眼变换 robot=R·cam+t", $"got=({robot[0]},{robot[1]},{robot[2]})");

            // ---- 4. 完整链路: 像素 + 深度 -> 机器人系 ----
            var full = CoordTransform.PixelToRobot(224.0, 152.0, 300.0);
            Assert(Near(full[0], -40) && Near(full[1], -230) && Near(full[2], -250),
                "完整链路 像素->相机->机器人 = (-40,-230,-250)", $"got=({full[0]:F1},{full[1]:F1},{full[2]:F1})");

            // ---- 5. 工作空间: 目标应在对齐原点后的区间内 ----
            Assert(Workspace.Contains(full), "工作空间对齐: 目标 (-40,-230,-250) 在区间内",
                $"bounds={Workspace.Describe()}");

            // ---- 6. 工作空间边界: 恰在边界内 ----
            Assert(Workspace.Contains(-180.0, -260.0, -350.0), "边界最小值(含) 在工作空间内");
            Assert(Workspace.Contains(-20.0, -140.0, -150.0), "边界最大值(含) 在工作空间内");

            // ---- 7. 工作空间边界: 恰越界 ----
            Assert(!Workspace.Contains(-180.01, -260.0, -350.0), "x 略低于下界被拒绝");
            Assert(!Workspace.Contains(-20.0, -139.99, -150.0), "y 略高于上界被拒绝");
            Assert(!Workspace.Contains(0.0, 0.0, 0.0), "名义原点(0,0,0) 不在对齐工作空间内 (原隐患)");

            // ---- 8. 数组空安全 ----
            Assert(!Workspace.Contains(new double[0]), "空数组返回 false 不抛异常");

            Console.WriteLine($"== 测试结果: 通过 {_passed}, 失败 {_failed} ==");
            return _failed == 0 ? 0 : 1;
        }
    }

    // =========================================================================
    // 入口
    // =========================================================================
    public static class Program
    {
        public static int Main(string[] args)
        {
            string mode = args.Length > 0 ? args[0].ToLowerInvariant() : "chain";

            switch (mode)
            {
                case "board":
                case "debug":
                    BoardDebug.Run();
                    break;
                case "chain":
                case "multi":
                    new HardwareChain().RunChain();
                    break;
                case "test":
                case "selftest":
                    return CoordinateTests.Run();
                default:
                    new HardwareChain().RunChain();
                    break;
            }
            return 0;
        }
    }
}
