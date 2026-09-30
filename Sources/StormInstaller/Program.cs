using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
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

            // Top-Right Header Icon (Clean Program Icon, without frames or borders - Rule 4)
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

            // Red-Black Signature Logo in Body (Clean, without frames/borders, directly below header icon - Rule 4)
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
                    if (name.EndsWith("logo.png", StringComparison.OrdinalIgnoreCase) ||
                        name.EndsWith("badge_logo.png", StringComparison.OrdinalIgnoreCase))
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
                // Rule 3: Installation strictly to program name folder WITHOUT version
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
                Font = new Font("Segoe UI", 9.5f, FontStyle.Regular),
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
            if (rbPortable.Checked)
            {
                txtInstallPath.Text = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, $"{AppFolderName}_Portable");
                chkDesktop.Checked = false;
                chkDesktop.Enabled = false;
                chkStartMenu.Checked = false;
                chkStartMenu.Enabled = false;
                chkRegister.Checked = false;
                chkRegister.Enabled = false;
                btnInstall.Text = "📦  Распаковать";
            }
            else
            {
                txtInstallPath.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppFolderName);
                chkDesktop.Checked = true;
                chkDesktop.Enabled = true;
                chkStartMenu.Checked = true;
                chkStartMenu.Enabled = true;
                chkRegister.Checked = true;
                chkRegister.Enabled = true;
                btnInstall.Text = "📦  Установить";
            }
        }

        private void BtnBrowse_Click(object? sender, EventArgs e)
        {
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
            progressBar.Visible = true;
            lblStatus.Visible = true;
            await StartInstallationAsync();
        }

        private async Task StartInstallationAsync()
        {
            // Rule 4: On start, Install button disables, Cancel button remains active
            btnInstall.Enabled = false;
            btnCancel.Enabled = true;
            btnBrowse.Enabled = false;
            rbStandard.Enabled = false;
            rbPortable.Enabled = false;
            txtInstallPath.Enabled = false;
            chkDesktop.Enabled = false;
            chkStartMenu.Enabled = false;
            chkInstallCert.Enabled = false;
            chkRegister.Enabled = false;
            chkRunAfter.Enabled = false;

            try
            {
                string targetDir = txtInstallPath.Text.Trim();
                if (string.IsNullOrEmpty(targetDir))
                {
                    targetDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), AppFolderName);
                }

                Directory.CreateDirectory(targetDir);

                lblStatus.Text = "Завершение предыдущих процессов программы...";
                progressBar.Value = 10;
                await Task.Delay(150);

                KillRunningProcesses();

                string targetExe = Path.Combine(targetDir, ExeName);
                string targetCer = Path.Combine(targetDir, "STORM_Certificate.cer");
                string targetIco = Path.Combine(targetDir, IcoName);
                string targetLogo = Path.Combine(targetDir, "logo.png");

                if (chkInstallCert.Checked)
                {
                    lblStatus.Text = "Регистрация доверенного сертификата...";
                    progressBar.Value = 25;
                    await Task.Delay(150);

                    try
                    {
                        ExtractResource("STORM_Certificate.cer", targetCer);
                        if (File.Exists(targetCer))
                        {
                            InstallCertificateSilently(targetCer);
                        }
                    }
                    catch { }
                }

                lblStatus.Text = $"Распаковка пакета {AppDisplayName} (v{AppVersion})...";
                progressBar.Value = 45;
                await Task.Delay(100);

                ExtractResource(ExeName, targetExe);
                try { ExtractResource(IcoName, targetIco); } catch { }
                try { ExtractResource("logo.png", targetLogo); } catch { }

                // Extract Tools directory
                ExtractAllToolFiles(targetDir);

                progressBar.Value = 75;
                lblStatus.Text = "Снятие меток блокировки и оптимизация безопасности...";
                await Task.Delay(150);

                UnblockFile(targetExe);
                UnblockFile(targetCer);
                UnblockFile(targetIco);
                UnblockFile(targetLogo);
                UnblockEntireDirectory(targetDir);

                if (rbStandard.Checked)
                {
                    lblStatus.Text = "Создание системных ярлыков и регистрация в Windows...";
                    progressBar.Value = 88;
                    await Task.Delay(150);

                    CreateShortcuts(targetDir, targetExe, targetIco, chkDesktop.Checked, chkStartMenu.Checked);

                    if (chkRegister.Checked)
                    {
                        RegisterUninstall(targetDir, targetExe, targetIco);
                    }
                }

                // Rule 4: At 100%, both buttons are disabled, installer auto-launches program and closes
                progressBar.Value = 100;
                lblStatus.Text = rbPortable.Checked ? "Портативная версия успешно распакована!" : "Установка успешно завершена! Система полностью готова.";
                lblStatus.ForeColor = Color.FromArgb(16, 185, 129);
                btnInstall.Enabled = false;
                btnCancel.Enabled = false;
                await Task.Delay(500);

                if (chkRunAfter.Checked)
                {
                    TryLaunchApplication(targetExe, targetDir);
                }

                this.Close();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Ошибка во время установки:\n{ex.Message}", "Ошибка установки", MessageBoxButtons.OK, MessageBoxIcon.Error);
                btnInstall.Enabled = true;
                btnCancel.Enabled = true;
                btnBrowse.Enabled = true;
            }
        }

        private void ExtractAllToolFiles(string targetDir)
        {
            string toolsTargetDir = Path.Combine(targetDir, "tools");
            Directory.CreateDirectory(toolsTargetDir);

            var asm = Assembly.GetExecutingAssembly();
            foreach (var name in asm.GetManifestResourceNames())
            {
                if (name.Contains(".tools.", StringComparison.OrdinalIgnoreCase))
                {
                    int idx = name.IndexOf(".tools.", StringComparison.OrdinalIgnoreCase);
                    string relPath = name.Substring(idx + 7);
                    
                    string fullOutPath = Path.Combine(toolsTargetDir, relPath);
                    string? dir = Path.GetDirectoryName(fullOutPath);
                    if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

                    using var s = asm.GetManifestResourceStream(name);
                    if (s != null)
                    {
                        using var fs = new FileStream(fullOutPath, FileMode.Create, FileAccess.Write);
                        s.CopyTo(fs);
                    }
                }
            }
        }

        private static void TryLaunchApplication(string directExePath, string workingDir)
        {
            try
            {
                if (File.Exists(directExePath))
                {
                    UnblockFile(directExePath);
                    try
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = directExePath,
                            WorkingDirectory = workingDir,
                            UseShellExecute = true
                        });
                        return;
                    }
                    catch { }
                }
            }
            catch { }
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

        public static void UnblockEntireDirectory(string dirPath)
        {
            try
            {
                if (Directory.Exists(dirPath))
                {
                    foreach (var file in Directory.GetFiles(dirPath, "*.*", SearchOption.AllDirectories))
                    {
                        UnblockFile(file);
                    }
                }
            }
            catch { }
        }

        private static void KillRunningProcesses()
        {
            string[] procNames = { "STORM PS4 PKG SENDER", "stormps4pkgsender", "ps4_pkg_sender" };
            foreach (var pName in procNames)
            {
                try
                {
                    foreach (var p in Process.GetProcessesByName(pName))
                    {
                        try
                        {
                            p.Kill();
                            p.WaitForExit(1000);
                        }
                        catch { }
                    }
                }
                catch { }
            }
        }

        private static void ExtractResource(string resSubname, string targetPath)
        {
            var asm = Assembly.GetExecutingAssembly();
            string? foundName = null;
            foreach (var name in asm.GetManifestResourceNames())
            {
                if (name.EndsWith(resSubname, StringComparison.OrdinalIgnoreCase))
                {
                    foundName = name;
                    break;
                }
            }

            if (foundName == null) return;

            string? dir = Path.GetDirectoryName(targetPath);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            using var s = asm.GetManifestResourceStream(foundName);
            if (s == null) return;

            using var fs = new FileStream(targetPath, FileMode.Create, FileAccess.Write);
            s.CopyTo(fs);
        }

        private static void InstallCertificateSilently(string certPath)
        {
            try
            {
                var cert = new X509Certificate2(certPath);
                using (var store = new X509Store(StoreName.Root, StoreLocation.LocalMachine))
                {
                    store.Open(OpenFlags.ReadWrite);
                    store.Add(cert);
                    store.Close();
                }
                using (var store = new X509Store(StoreName.TrustedPublisher, StoreLocation.LocalMachine))
                {
                    store.Open(OpenFlags.ReadWrite);
                    store.Add(cert);
                    store.Close();
                }
            }
            catch
            {
                try
                {
                    var cert = new X509Certificate2(certPath);
                    using (var store = new X509Store(StoreName.Root, StoreLocation.CurrentUser))
                    {
                        store.Open(OpenFlags.ReadWrite);
                        store.Add(cert);
                        store.Close();
                    }
                    using (var store = new X509Store(StoreName.TrustedPublisher, StoreLocation.CurrentUser))
                    {
                        store.Open(OpenFlags.ReadWrite);
                        store.Add(cert);
                        store.Close();
                    }
                }
                catch { }
            }
        }

        private static void CreateShortcuts(string targetDir, string exePath, string icoPath, bool desktop, bool startMenu)
        {
            Type? shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType == null) return;

            dynamic? shell = Activator.CreateInstance(shellType);
            if (shell == null) return;

            if (desktop)
            {
                try
                {
                    string deskDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    string lnkPath = Path.Combine(deskDir, $"{AppDisplayName}.lnk");
                    dynamic shortcut = shell.CreateShortcut(lnkPath);
                    shortcut.TargetPath = exePath;
                    shortcut.WorkingDirectory = targetDir;
                    shortcut.IconLocation = icoPath;
                    shortcut.Description = $"{AppDisplayName} v{AppVersion}";
                    shortcut.Save();
                }
                catch { }
            }

            if (startMenu)
            {
                try
                {
                    string progDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms), "STORM SOFT");
                    Directory.CreateDirectory(progDir);
                    string lnkPath = Path.Combine(progDir, $"{AppDisplayName}.lnk");
                    dynamic shortcut = shell.CreateShortcut(lnkPath);
                    shortcut.TargetPath = exePath;
                    shortcut.WorkingDirectory = targetDir;
                    shortcut.IconLocation = icoPath;
                    shortcut.Description = $"{AppDisplayName} v{AppVersion}";
                    shortcut.Save();
                }
                catch { }
            }
        }

        private static void RegisterUninstall(string targetDir, string exePath, string icoPath)
        {
            try
            {
                // Create clean Uninstall.bat
                string uninstBat = Path.Combine(targetDir, "Uninstall.bat");
                string batContent = $@"@echo off
taskkill /F /IM ""{ExeName}"" >nul 2>&1
timeout /t 1 /nobreak >nul
del /f /q ""{Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), $"{AppDisplayName}.lnk")}"" >nul 2>&1
rmdir /s /q ""{Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonPrograms), "STORM SOFT")}"" >nul 2>&1
reg delete ""HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppFolderName}"" /f >nul 2>&1
echo Программа {AppDisplayName} успешно удалена.
";
                File.WriteAllText(uninstBat, batContent);

                using var key = Registry.LocalMachine.CreateSubKey($@"Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppFolderName}");
                if (key != null)
                {
                    key.SetValue("DisplayName", AppDisplayName);
                    key.SetValue("DisplayVersion", AppVersion);
                    key.SetValue("Publisher", "ReiKatari");
                    key.SetValue("DisplayIcon", icoPath);
                    key.SetValue("InstallLocation", targetDir);
                    key.SetValue("UninstallString", $"cmd.exe /c \"{uninstBat}\"");
                    key.SetValue("QuietUninstallString", $"cmd.exe /c \"{uninstBat}\"");
                    key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                }
            }
            catch
            {
                try
                {
                    using var key = Registry.CurrentUser.CreateSubKey($@"Software\Microsoft\Windows\CurrentVersion\Uninstall\{AppFolderName}");
                    if (key != null)
                    {
                        key.SetValue("DisplayName", AppDisplayName);
                        key.SetValue("DisplayVersion", AppVersion);
                        key.SetValue("Publisher", "ReiKatari");
                        key.SetValue("DisplayIcon", icoPath);
                        key.SetValue("InstallLocation", targetDir);
                    }
                }
                catch { }
            }
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new InstallerForm());
        }
    }
}
