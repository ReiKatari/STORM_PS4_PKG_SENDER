using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

namespace StormUniversal.Installer
{
    public class InstallerForm : Form
    {
        private ProgressBar progressBar = null!;
        private Label lblStatus = null!;
        private Label lblTitle = null!;
        private Label lblSubtitle = null!;
        private Button btnInstall = null!;
        private Button btnCancel = null!;
        private PictureBox picHeaderLogo = null!;
        private Panel headerPanel = null!;

        private const string AppVersion = "1.4.0";
        private const string AppDisplayName = "STORM PS4 PKG SENDER";
        private const string AppFolderName = "STORM PS4 PKG SENDER";
        private const string ExeName = "STORM PS4 PKG SENDER.exe";
        private const string IcoName = "AppIcon.ico";

        private RadioButton rbStandard = null!;
        private RadioButton rbPortable = null!;
        private TextBox txtInstallPath = null!;
        private Button btnBrowse = null!;

        private CheckBox chkDesktop = null!;
        private CheckBox chkStartMenu = null!;
        private CheckBox chkRegister = null!;
        private CheckBox chkInstallCert = null!;
        private CheckBox chkRunAfter = null!;
        private bool isInstalling = false;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool DeleteFile(string name);

        public InstallerForm()
        {
            try
            {
                var asm = Assembly.GetExecutingAssembly();
                foreach (var name in asm.GetManifestResourceNames())
                {
                    if (name.EndsWith(IcoName, StringComparison.OrdinalIgnoreCase) || name.EndsWith("app.ico", StringComparison.OrdinalIgnoreCase))
                    {
                        using var s = asm.GetManifestResourceStream(name);
                        if (s != null)
                        {
                            this.Icon = new Icon(s);
                            break;
                        }
                    }
                }
                if (this.Icon == null && !string.IsNullOrEmpty(Application.ExecutablePath) && File.Exists(Application.ExecutablePath))
                {
                    this.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
                }
            }
            catch { }
            InitializeComponent();
        }

        private static GraphicsPath GetRoundedRectPath(Rectangle rect, int radius)
        {
            GraphicsPath path = new GraphicsPath();
            int diameter = radius * 2;
            Rectangle arc = new Rectangle(rect.Location, new Size(diameter, diameter));

            // top left
            path.AddArc(arc, 180, 90);
            // top right
            arc.X = rect.Right - diameter;
            path.AddArc(arc, 270, 90);
            // bottom right
            arc.Y = rect.Bottom - diameter;
            path.AddArc(arc, 0, 90);
            // bottom left
            arc.X = rect.Left;
            path.AddArc(arc, 90, 90);
            path.CloseFigure();
            return path;
        }

        private void InitializeComponent()
        {
            this.Text = $"{AppDisplayName} — STORM INSTALLER";
            this.Size = new Size(640, 540);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.BackColor = Color.FromArgb(11, 15, 25);
            this.ForeColor = Color.White;
            this.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);

            // 1. Dark Stylized Header
            headerPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 88,
                BackColor = Color.FromArgb(17, 24, 39),
                Padding = new Padding(22, 14, 22, 14)
            };
            headerPanel.Paint += (s, e) =>
            {
                // Bottom Cyan Accent Line
                using var p = new Pen(Color.FromArgb(14, 165, 233), 2f);
                e.Graphics.DrawLine(p, 0, headerPanel.Height - 1, headerPanel.Width, headerPanel.Height - 1);
            };

            lblTitle = new Label
            {
                Text = AppDisplayName,
                Font = new Font("Segoe UI", 15.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(14, 165, 233),
                AutoSize = true,
                Location = new Point(22, 16)
            };

            lblSubtitle = new Label
            {
                Text = $"Мастер установки • Версия {AppVersion} • STORM TEAM",
                Font = new Font("Segoe UI", 9.2f, FontStyle.Regular),
                ForeColor = Color.FromArgb(156, 163, 175),
                AutoSize = true,
                Location = new Point(24, 49)
            };

            // Top-Right Header Icon (Clean Program Icon, without frames or borders)
            picHeaderLogo = new PictureBox
            {
                Location = new Point(548, 16),
                Size = new Size(54, 54),
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.Transparent
            };

            if (this.Icon != null)
            {
                picHeaderLogo.Image = this.Icon.ToBitmap();
            }

            headerPanel.Controls.Add(lblTitle);
            headerPanel.Controls.Add(lblSubtitle);
            headerPanel.Controls.Add(picHeaderLogo);
            this.Controls.Add(headerPanel);

            // 2. Body Panel
            var bodyPanel = new Panel
            {
                Location = new Point(24, 98),
                Size = new Size(576, 350)
            };

            // Red-Black Signature Logo in Body (Clean, without frames/borders, directly below header icon)
            var picBodyLogo = new PictureBox
            {
                Location = new Point(524, 10),
                Size = new Size(54, 54),
                SizeMode = PictureBoxSizeMode.Zoom,
                BackColor = Color.Transparent
            };

            Image? logoImg = null;
            try
            {
                var asm = Assembly.GetExecutingAssembly();
                foreach (var name in asm.GetManifestResourceNames())
                {
                    if (name.EndsWith("header_badge.png", StringComparison.OrdinalIgnoreCase) ||
                        name.EndsWith("badge_logo.png", StringComparison.OrdinalIgnoreCase) ||
                        name.EndsWith("logo.png", StringComparison.OrdinalIgnoreCase))
                    {
                        using var s = asm.GetManifestResourceStream(name);
                        if (s != null)
                        {
                            logoImg = Image.FromStream(s);
                            break;
                        }
                    }
                }
            }
            catch { }

            if (logoImg != null)
            {
                picBodyLogo.Image = logoImg;
                bodyPanel.Controls.Add(picBodyLogo);
            }

            var lblMode = new Label
            {
                Text = "Выберите тип установки программы:",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(226, 232, 240),
                Location = new Point(0, 0),
                AutoSize = true
            };
            bodyPanel.Controls.Add(lblMode);

            rbStandard = new RadioButton
            {
                Text = "Стандартная установка в Program Files (рекомендуется)",
                Checked = true,
                Location = new Point(10, 25),
                AutoSize = true,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
                ForeColor = Color.White
            };
            rbStandard.CheckedChanged += Mode_CheckedChanged;
            bodyPanel.Controls.Add(rbStandard);

            rbPortable = new RadioButton
            {
                Text = "Портативная версия (в выбранную вами папку, без реестра)",
                Checked = false,
                Location = new Point(10, 50),
                AutoSize = true,
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
                ForeColor = Color.White
            };
            rbPortable.CheckedChanged += Mode_CheckedChanged;
            bodyPanel.Controls.Add(rbPortable);

            var lblPath = new Label
            {
                Text = "Папка назначения:",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(226, 232, 240),
                Location = new Point(0, 82),
                AutoSize = true
            };
            bodyPanel.Controls.Add(lblPath);

            txtInstallPath = new TextBox
            {
                Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppFolderName),
                Location = new Point(5, 105),
                Size = new Size(460, 26),
                BackColor = Color.FromArgb(17, 24, 39),
                ForeColor = Color.White,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Segoe UI", 9.5f)
            };
            bodyPanel.Controls.Add(txtInstallPath);

            btnBrowse = new Button
            {
                Text = "Обзор...",
                Location = new Point(475, 104),
                Size = new Size(95, 28),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(30, 41, 59),
                ForeColor = Color.FromArgb(14, 165, 233),
                Cursor = Cursors.Hand
            };
            btnBrowse.FlatAppearance.BorderColor = Color.FromArgb(14, 165, 233);
            btnBrowse.Click += BtnBrowse_Click;
            bodyPanel.Controls.Add(btnBrowse);

            var lblOptions = new Label
            {
                Text = "Дополнительные параметры безопасности и интеграции:",
                Font = new Font("Segoe UI", 9.5f, FontStyle.Bold),
                ForeColor = Color.FromArgb(226, 232, 240),
                Location = new Point(0, 142),
                AutoSize = true
            };
            bodyPanel.Controls.Add(lblOptions);

            chkDesktop = new CheckBox
            {
                Text = "Создать ярлык на Рабочем столе",
                Checked = true,
                Location = new Point(10, 166),
                AutoSize = true,
                ForeColor = Color.White
            };
            bodyPanel.Controls.Add(chkDesktop);

            chkStartMenu = new CheckBox
            {
                Text = "Создать ярлык в меню «Пуск»",
                Checked = true,
                Location = new Point(10, 191),
                AutoSize = true,
                ForeColor = Color.White
            };
            bodyPanel.Controls.Add(chkStartMenu);

            chkInstallCert = new CheckBox
            {
                Text = "Зарегистрировать сертификат STORM TEAM (защита от SmartScreen / SAC)",
                Checked = true,
                Location = new Point(10, 216),
                AutoSize = true,
                ForeColor = Color.FromArgb(52, 211, 153)
            };
            bodyPanel.Controls.Add(chkInstallCert);

            chkRegister = new CheckBox
            {
                Text = "Зарегистрировать в списке «Установка и удаление программ»",
                Checked = true,
                Location = new Point(10, 241),
                AutoSize = true,
                ForeColor = Color.White
            };
            bodyPanel.Controls.Add(chkRegister);

            chkRunAfter = new CheckBox
            {
                Text = $"Запустить {AppDisplayName} сразу после установки",
                Checked = true,
                Location = new Point(10, 266),
                AutoSize = true,
                ForeColor = Color.FromArgb(14, 165, 233)
            };
            bodyPanel.Controls.Add(chkRunAfter);

            progressBar = new ProgressBar
            {
                Location = new Point(5, 296),
                Size = new Size(565, 12),
                Style = ProgressBarStyle.Continuous,
                Value = 0,
                Visible = false
            };
            bodyPanel.Controls.Add(progressBar);

            lblStatus = new Label
            {
                Text = "",
                Location = new Point(5, 312),
                Size = new Size(565, 20),
                Font = new Font("Segoe UI", 8.8f),
                ForeColor = Color.FromArgb(148, 163, 184),
                Visible = false
            };
            bodyPanel.Controls.Add(lblStatus);

            this.Controls.Add(bodyPanel);

            // 3. Bottom Panel
            var bottomPanel = new Panel
            {
                Dock = DockStyle.Bottom,
                Height = 60,
                BackColor = Color.FromArgb(17, 24, 39),
                Padding = new Padding(24, 12, 24, 12)
            };

            btnCancel = new Button
            {
                Text = "Отмена",
                Size = new Size(110, 36),
                Location = new Point(365, 12),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(30, 41, 59),
                ForeColor = Color.FromArgb(226, 232, 240),
                Cursor = Cursors.Hand
            };
            btnCancel.FlatAppearance.BorderColor = Color.FromArgb(51, 65, 85);
            btnCancel.Click += (s, e) => this.Close();
            bottomPanel.Controls.Add(btnCancel);

            btnInstall = new Button
            {
                Text = "📦  Установить",
                Size = new Size(135, 36),
                Location = new Point(485, 12),
                FlatStyle = FlatStyle.Flat,
                BackColor = Color.FromArgb(14, 165, 233),
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9.8f, FontStyle.Bold),
                Cursor = Cursors.Hand
            };
            btnInstall.FlatAppearance.BorderColor = Color.FromArgb(56, 189, 248);
            btnInstall.Click += BtnInstall_Click;
            bottomPanel.Controls.Add(btnInstall);

            this.Controls.Add(bottomPanel);
        }

        private void Mode_CheckedChanged(object? sender, EventArgs e)
        {
            if (isInstalling) return;
            if (rbPortable.Checked)
            {
                txtInstallPath.Text = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, $"{AppFolderName}_Portable");
                chkDesktop.Checked = false;
                chkDesktop.AutoCheck = false;
                chkDesktop.ForeColor = Color.FromArgb(100, 116, 139);
                chkDesktop.Cursor = Cursors.Default;

                chkStartMenu.Checked = false;
                chkStartMenu.AutoCheck = false;
                chkStartMenu.ForeColor = Color.FromArgb(100, 116, 139);
                chkStartMenu.Cursor = Cursors.Default;

                chkRegister.Checked = false;
                chkRegister.AutoCheck = false;
                chkRegister.ForeColor = Color.FromArgb(100, 116, 139);
                chkRegister.Cursor = Cursors.Default;

                btnInstall.Text = "📦  Распаковать";
            }
            else
            {
                txtInstallPath.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppFolderName);
                chkDesktop.Checked = true;
                chkDesktop.AutoCheck = true;
                chkDesktop.ForeColor = Color.White;
                chkDesktop.Cursor = Cursors.Hand;

                chkStartMenu.Checked = true;
                chkStartMenu.AutoCheck = true;
                chkStartMenu.ForeColor = Color.White;
                chkStartMenu.Cursor = Cursors.Hand;

                chkRegister.Checked = true;
                chkRegister.AutoCheck = true;
                chkRegister.ForeColor = Color.White;
                chkRegister.Cursor = Cursors.Hand;

                btnInstall.Text = "📦  Установить";
            }
        }

        private void BtnBrowse_Click(object? sender, EventArgs e)
        {
            if (isInstalling) return;
            using var fbd = new FolderBrowserDialog();
            fbd.Description = $"Выберите папку для установки {AppDisplayName}:";
            fbd.UseDescriptionForTitle = true;
            if (fbd.ShowDialog() == DialogResult.OK)
            {
                txtInstallPath.Text = fbd.SelectedPath;
            }
        }

        private async void BtnInstall_Click(object? sender, EventArgs e)
        {
            if (isInstalling) return;
            progressBar.Visible = true;
            lblStatus.Visible = true;
            await StartInstallationAsync();
        }

        private async Task StartInstallationAsync()
        {
            isInstalling = true;

            btnInstall.Enabled = false;
            btnInstall.BackColor = Color.FromArgb(30, 41, 59);
            btnInstall.ForeColor = Color.FromArgb(100, 116, 139);
            btnInstall.FlatAppearance.BorderColor = Color.FromArgb(51, 65, 85);
            btnInstall.Cursor = Cursors.Default;

            btnCancel.Enabled = true;

            btnBrowse.Cursor = Cursors.Default;
            btnBrowse.ForeColor = Color.FromArgb(100, 116, 139);
            btnBrowse.BackColor = Color.FromArgb(20, 28, 40);
            btnBrowse.FlatAppearance.BorderColor = Color.FromArgb(51, 65, 85);

            rbStandard.AutoCheck = false;
            rbPortable.AutoCheck = false;
            txtInstallPath.ReadOnly = true;

            chkDesktop.AutoCheck = false;
            chkStartMenu.AutoCheck = false;
            chkInstallCert.AutoCheck = false;
            chkRegister.AutoCheck = false;
            chkRunAfter.AutoCheck = false;

            try
            {
                string targetDir = txtInstallPath.Text.Trim();
                if (string.IsNullOrEmpty(targetDir))
                {
                    targetDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppFolderName);
                }

                Directory.CreateDirectory(targetDir);

                // Terminate any running instances
                lblStatus.Text = "Завершение предыдущих процессов программы...";
                progressBar.Value = 10;
                await Task.Delay(150);

                foreach (var p in Process.GetProcessesByName("STORM PS4 PKG SENDER"))
                {
                    try { p.Kill(); p.WaitForExit(1500); } catch { }
                }
                foreach (var p in Process.GetProcessesByName("stormps4pkgsender"))
                {
                    try { p.Kill(); p.WaitForExit(1500); } catch { }
                }

                string targetExe = Path.Combine(targetDir, ExeName);
                string targetCer = Path.Combine(targetDir, "STORM_Certificate.cer");
                string targetIco = Path.Combine(targetDir, IcoName);
                string targetLogo = Path.Combine(targetDir, "logo.png");

                if (!Directory.Exists(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                if (chkInstallCert.Checked)
                {
                    lblStatus.Text = "Регистрация доверенного сертификата (Root и Publisher)...";
                    progressBar.Value = 25;
                    await Task.Delay(150);

                    ExtractResource("STORM_Certificate.cer", targetCer);
                    if (File.Exists(targetCer))
                    {
                        InstallCertificateSilently(targetCer);
                    }
                }

                lblStatus.Text = $"Распаковка пакета {AppDisplayName} ({AppVersion})...";
                progressBar.Value = 35;
                await Task.Delay(100);

                // Extract Zip Package
                await Task.Run(() =>
                {
                    var asm = Assembly.GetExecutingAssembly();
                    foreach (var name in asm.GetManifestResourceNames())
                    {
                        if (name.EndsWith("Payload.zip", StringComparison.OrdinalIgnoreCase) || name.EndsWith("publish.zip", StringComparison.OrdinalIgnoreCase))
                        {
                            using var stream = asm.GetManifestResourceStream(name);
                            if (stream != null)
                            {
                                using var zip = new ZipArchive(stream, ZipArchiveMode.Read);
                                int total = zip.Entries.Count;
                                int count = 0;
                                foreach (var entry in zip.Entries)
                                {
                                    count++;
                                    string destPath = Path.Combine(targetDir, entry.FullName);
                                    if (string.IsNullOrEmpty(entry.Name))
                                    {
                                        Directory.CreateDirectory(destPath);
                                        continue;
                                    }

                                    string? parent = Path.GetDirectoryName(destPath);
                                    if (!string.IsNullOrEmpty(parent)) Directory.CreateDirectory(parent);

                                    if (File.Exists(destPath))
                                    {
                                        try
                                        {
                                            File.SetAttributes(destPath, FileAttributes.Normal);
                                            File.Delete(destPath);
                                        }
                                        catch { }
                                    }

                                    entry.ExtractToFile(destPath, true);
                                    UnblockFile(destPath);

                                    int percent = 35 + (int)((double)count / total * 45);
                                    this.Invoke((System.Windows.Forms.MethodInvoker)delegate
                                    {
                                        if (percent <= 80) progressBar.Value = percent;
                                    });
                                }
                            }
                            break;
                        }
                    }
                });

                ExtractResource(IcoName, targetIco);
                ExtractResource("header_badge.png", targetLogo);
                ExtractResource("STORM_Certificate.cer", targetCer);

                // Self-healing: Unblock files and remove Mark of the Web
                lblStatus.Text = "Снятие меток блокировки и оптимизация безопасности...";
                progressBar.Value = 85;
                await Task.Delay(100);

                UnblockFile(targetExe);
                UnblockFile(targetCer);
                UnblockFile(targetIco);
                UnblockFile(targetLogo);
                UnblockEntireDirectory(targetDir);

                if (rbStandard.Checked)
                {
                    lblStatus.Text = "Создание системных ярлыков и регистрация в Windows...";
                    progressBar.Value = 92;
                    await Task.Delay(150);

                    CreateShortcuts(targetDir, targetExe, targetIco, chkDesktop.Checked, chkStartMenu.Checked);

                    if (chkRegister.Checked)
                    {
                        RegisterUninstall(targetDir, targetExe, targetIco);
                    }
                }

                progressBar.Value = 100;
                lblStatus.Text = rbPortable.Checked ? "Портативная версия успешно распакована и разблокирована!" : "Установка успешно завершена! Система полностью готова.";
                lblStatus.ForeColor = Color.FromArgb(16, 185, 129);
                btnInstall.Enabled = false;
                btnInstall.BackColor = Color.FromArgb(20, 28, 40);
                btnInstall.ForeColor = Color.FromArgb(80, 95, 115);
                btnCancel.Enabled = false;
                btnCancel.BackColor = Color.FromArgb(20, 28, 40);
                btnCancel.ForeColor = Color.FromArgb(80, 95, 115);
                btnCancel.Cursor = Cursors.Default;
                await Task.Delay(500);

                if (chkRunAfter.Checked && File.Exists(targetExe))
                {
                    try
                    {
                        // Запуск через explorer.exe гарантирует нормальный (неповышенный) уровень привилегий (Medium IL),
                        // что полностью исключает блокировку Drag-and-Drop механизмом UIPI в Windows
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = "explorer.exe",
                            Arguments = $"\"{targetExe}\"",
                            UseShellExecute = true
                        });
                    }
                    catch
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = targetExe,
                            WorkingDirectory = targetDir,
                            UseShellExecute = true
                        });
                    }
                }

                this.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Ошибка во время установки:\n{ex.Message}", "Ошибка установки", MessageBoxButtons.OK, MessageBoxIcon.Error);
                isInstalling = false;

                btnInstall.Enabled = true;
                btnInstall.BackColor = Color.FromArgb(14, 165, 233);
                btnInstall.ForeColor = Color.White;
                btnInstall.FlatAppearance.BorderColor = Color.FromArgb(56, 189, 248);
                btnInstall.Cursor = Cursors.Hand;

                btnCancel.Enabled = true;

                btnBrowse.Cursor = Cursors.Hand;
                btnBrowse.ForeColor = Color.FromArgb(14, 165, 233);
                btnBrowse.BackColor = Color.FromArgb(30, 41, 59);
                btnBrowse.FlatAppearance.BorderColor = Color.FromArgb(14, 165, 233);

                rbStandard.AutoCheck = true;
                rbPortable.AutoCheck = true;
                txtInstallPath.ReadOnly = false;

                if (rbStandard.Checked)
                {
                    chkDesktop.AutoCheck = true;
                    chkStartMenu.AutoCheck = true;
                    chkRegister.AutoCheck = true;
                }
                chkInstallCert.AutoCheck = true;
                chkRunAfter.AutoCheck = true;
            }
        }

        public static void UnblockFile(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    DeleteFile(path + ":Zone.Identifier");
                }
            }
            catch { }
        }

        public static void UnblockEntireDirectory(string dir)
        {
            try
            {
                if (!Directory.Exists(dir)) return;
                foreach (var file in Directory.GetFiles(dir, "*.*", SearchOption.AllDirectories))
                {
                    UnblockFile(file);
                }
            }
            catch { }
        }

        public static void InstallCertificateSilently(string cerPath)
        {
            try
            {
                if (!File.Exists(cerPath)) return;

                // 1. Direct certutil command (fastest and most reliable on Windows)
                try
                {
                    var psiRoot = new ProcessStartInfo
                    {
                        FileName = "certutil.exe",
                        Arguments = $"-addstore -f \"Root\" \"{cerPath}\"",
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WindowStyle = ProcessWindowStyle.Hidden
                    };
                    using var p1 = Process.Start(psiRoot);
                    p1?.WaitForExit(5000);

                    var psiPub = new ProcessStartInfo
                    {
                        FileName = "certutil.exe",
                        Arguments = $"-addstore -f \"TrustedPublisher\" \"{cerPath}\"",
                        UseShellExecute = false,
                        CreateNoWindow = true,
                        WindowStyle = ProcessWindowStyle.Hidden
                    };
                    using var p2 = Process.Start(psiPub);
                    p2?.WaitForExit(5000);
                }
                catch { }

                // 2. .NET X509Store fallback
                try
                {
                    var cert = new X509Certificate2(cerPath);
                    using (var lmRoot = new X509Store(StoreName.Root, StoreLocation.LocalMachine))
                    {
                        lmRoot.Open(OpenFlags.ReadWrite);
                        lmRoot.Add(cert);
                    }
                    using (var lmPub = new X509Store(StoreName.TrustedPublisher, StoreLocation.LocalMachine))
                    {
                        lmPub.Open(OpenFlags.ReadWrite);
                        lmPub.Add(cert);
                    }
                    using (var userPub = new X509Store(StoreName.TrustedPublisher, StoreLocation.CurrentUser))
                    {
                        userPub.Open(OpenFlags.ReadWrite);
                        userPub.Add(cert);
                    }
                }
                catch { }
            }
            catch { }
        }

        private void ExtractResource(string resNameEnding, string targetPath)
        {
            try
            {
                string? dir = Path.GetDirectoryName(targetPath);
                if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                {
                    Directory.CreateDirectory(dir);
                }
                var asm = Assembly.GetExecutingAssembly();
                foreach (var name in asm.GetManifestResourceNames())
                {
                    if (name.EndsWith(resNameEnding, StringComparison.OrdinalIgnoreCase))
                    {
                        using var inStream = asm.GetManifestResourceStream(name);
                        if (inStream != null)
                        {
                            using var outStream = File.Create(targetPath);
                            inStream.CopyTo(outStream);
                        }
                        return;
                    }
                }
            }
            catch { }
        }

        private void CreateShortcuts(string targetDir, string targetExe, string targetIco, bool desktopShortcut, bool startMenuShortcut)
        {
            try
            {
                Type? shellType = Type.GetTypeFromProgID("WScript.Shell");
                if (shellType == null) return;
                dynamic? shell = Activator.CreateInstance(shellType);
                if (shell == null) return;

                // Start Menu shortcut
                if (startMenuShortcut)
                {
                    string startMenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), $"{AppDisplayName}.lnk");
                    dynamic shortcut = shell.CreateShortcut(startMenu);
                    shortcut.TargetPath = targetExe;
                    shortcut.WorkingDirectory = targetDir;
                    shortcut.IconLocation = (File.Exists(targetIco) ? targetIco : targetExe) + ",0";
                    shortcut.Description = AppDisplayName;
                    shortcut.Save();
                }

                // Desktop shortcut
                if (desktopShortcut)
                {
                    string desktop = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), $"{AppDisplayName}.lnk");
                    dynamic deskShortcut = shell.CreateShortcut(desktop);
                    deskShortcut.TargetPath = targetExe;
                    deskShortcut.WorkingDirectory = targetDir;
                    deskShortcut.IconLocation = (File.Exists(targetIco) ? targetIco : targetExe) + ",0";
                    deskShortcut.Description = AppDisplayName;
                    deskShortcut.Save();
                }
            }
            catch { }
        }

        private void RegisterUninstall(string targetDir, string targetExe, string targetIco)
        {
            try
            {
                using var key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\StormPs4PkgSender");
                if (key != null)
                {
                    key.SetValue("DisplayName", AppDisplayName);
                    key.SetValue("DisplayVersion", AppVersion);
                    key.SetValue("Publisher", "STORM TEAM");
                    key.SetValue("DisplayIcon", File.Exists(targetIco) ? targetIco : targetExe);
                    key.SetValue("InstallLocation", targetDir);
                    key.SetValue("UninstallString", $"cmd.exe /c rmdir /s /q \"{targetDir}\" & del \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\*{AppDisplayName}*.lnk\" & del \"%USERPROFILE%\\Desktop\\*{AppDisplayName}*.lnk\"");
                }
            }
            catch { }
        }

        private static bool IsAdministrator()
        {
            try
            {
                using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
                var principal = new System.Security.Principal.WindowsPrincipal(identity);
                return principal.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch
            {
                return false;
            }
        }

        [STAThread]
        public static void Main()
        {
            try
            {
                string selfExe = Process.GetCurrentProcess().MainModule?.FileName ?? "";
                if (!string.IsNullOrEmpty(selfExe))
                {
                    UnblockFile(selfExe);
                }
            }
            catch { }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new InstallerForm());
        }
    }
}
