import dearpygui.dearpygui as dpg
from pathlib import Path
import threading
import queue
from datetime import datetime
import json
import sys
import logging
import subprocess
import tempfile
import os
import pytz
from PIL import Image
import numpy as np
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI

class BittyTaxGUI:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.processing = False
        self.selected_files = []
        self.current_file = None
        # Initialize LLM Chat feature
        self.ai_service = 'gemini'  # Set to 'gemini' to use Google Gemini instead
        self.ai_client = self._setup_ai_client()
        self.chat_history = []
        # Tax years range (2009-2025)
        self.tax_years = [year for year in range(2025, 2008, -1)]

        # International support constants
        self.currencies = [
            'GBP', 'USD', 'EUR', 'AUD', 'CAD', 'CHF', 'CNY', 'JPY',
            'NZD', 'SEK', 'KRW', 'SGD', 'HKD'
        ]

        # Common timezones
        self.timezones = sorted(pytz.all_timezones)

        # Tax rules
        self.tax_rules = ['UK_INDIVIDUAL'] + [
            f'UK_COMPANY_{month}' for month in [
                'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'
            ]
        ] + ['US_INDIVIDUAL_BETA']

        # Report types
        self.report_types = ["Full Report", "Audit Report", "Capital Gains Summary"]

        # Setup logging
        self.setup_logging()

        # Initialize GUI
        dpg.create_context()
        self.load_logo()

        # Create viewport with logo
        dpg.create_viewport(
            title="BittyTax Manager",
            width=1280,
            height=800,
            resizable=True,
            small_icon="assets/logo_small.ico",
            large_icon="assets/logo_large.ico"
        )
        dpg.set_viewport_vsync(True)

        self.setup_theme()
        self.setup_file_dialog()
        self.create_main_window()

        dpg.set_primary_window("Primary Window", True)
        dpg.setup_dearpygui()
        dpg.show_viewport()

    def setup_logging(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_filename = log_dir / f"bittytax_gui_{timestamp}.log"

        self.logger = logging.getLogger('BittyTaxGUI')
        self.logger.setLevel(logging.DEBUG)

        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        self.logger.info('BittyTax GUI application started')

    def load_logo(self):
        try:
            # Create assets directory if it doesn't exist
            assets_dir = Path("assets")
            assets_dir.mkdir(exist_ok=True)

            logo_path = assets_dir / "logo.png"
            icon_small = assets_dir / "logo_small.ico"
            icon_large = assets_dir / "logo_large.ico"

            if not logo_path.exists():
                self.logger.warning(f"Logo file missing: {logo_path}")
                return

            # Load and convert main logo
            image = Image.open(logo_path)
            image = image.convert('RGBA')  # Ensure RGBA format
            image = image.resize((64, 64))
            image_data = np.array(image)

            # Convert image data to float values (0-1 range)
            image_data = image_data.astype(np.float32) / 255.0

            with dpg.texture_registry():
                dpg.add_static_texture(
                    width=64,
                    height=64,
                    default_value=image_data.ravel(),
                    tag="logo_texture"
                )

            self.logger.info("Logo loaded successfully")

        except Exception as e:
            self.logger.error(f"Error loading logo: {str(e)}")

    def setup_theme(self):
        with dpg.theme() as self.main_theme:
            with dpg.theme_component(dpg.mvAll):
                # Window colors
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (15, 15, 15))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBgActive, (41, 120, 182))
                dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (30, 89, 135))

                # Button colors
                dpg.add_theme_color(dpg.mvThemeCol_Button, (41, 120, 182))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (59, 139, 203))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (33, 96, 145))

                # Header colors
                dpg.add_theme_color(dpg.mvThemeCol_Header, (41, 120, 182))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderHovered, (59, 139, 203))
                dpg.add_theme_color(dpg.mvThemeCol_HeaderActive, (33, 96, 145))

                # Tab colors
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (41, 120, 182))
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (59, 139, 203))
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (33, 96, 145))

                # Progress bar colors
                dpg.add_theme_color(dpg.mvThemeCol_PlotHistogram, (41, 120, 182))
                dpg.add_theme_color(dpg.mvThemeCol_PlotHistogramHovered, (59, 139, 203))

                # Styling
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 8)
                dpg.add_theme_style(dpg.mvStyleVar_GrabRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_TabRounding, 6)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 6, 6)
                dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowTitleAlign, 0.5, 0.5)

        dpg.bind_theme(self.main_theme)

    def setup_file_dialog(self):
        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            callback=self.file_dialog_callback,
            tag="file_dialog_tag",
            width=700,
            height=400,
            modal=True
        ):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".csv", color=(0, 255, 0, 255), custom_text="CSV Files")
            dpg.add_file_extension(".xlsx", color=(255, 255, 0, 255), custom_text="Excel Files")
            dpg.add_file_extension(".json", color=(0, 255, 255, 255), custom_text="JSON Files")

    def file_dialog_callback(self, sender, app_data):
        self.selected_files = list(app_data["selections"].values())
        if self.selected_files:
            self.current_file = self.selected_files[0]
            files_str = "\n".join(self.selected_files)
            self.logger.info(f"Selected files: {files_str}")
            dpg.set_value(self.log_window, f"Selected files:\n{files_str}")
            dpg.set_value(self.progress_bar, 0.0)

    def create_main_window(self):
        with dpg.window(tag="Primary Window"):
            # Add logo at the top with proper spacing
            if dpg.does_alias_exist("logo_texture"):
                with dpg.group(horizontal=True):
                    dpg.add_spacer(width=10)
                    dpg.add_image(
                        "logo_texture",
                        width=64,
                        height=64
                    )
                    dpg.add_spacer(width=10)
                    dpg.add_text(
                        "BittyTax Manager",
                        color=(41, 120, 182)
                    )

            dpg.add_separator()

            with dpg.tab_bar():
                self.create_import_tab()
                self.create_tax_tab()
                self.create_audit_tab()
                self.create_international_tab()
                self.create_settings_tab()
                self.create_llm_chat_tab()


    def process_files(self):
        if not self.selected_files:
            self.logger.warning("No files selected for processing")
            dpg.set_value(self.log_window, "Please select files first")
            return

        if self.processing:
            self.logger.warning("Processing already in progress")
            return

        self.processing = True
        self.logger.info("Starting file processing")

        def process_worker():
            try:
                total_files = len(self.selected_files)
                for i, file_path in enumerate(self.selected_files):
                    progress = (i + 1) / total_files
                    self.message_queue.put((f"Processing {file_path}...", progress))
                    output = self.run_bittytax_command(None)
                    self.message_queue.put((f"Processed {file_path}\n{output}", progress))
                self.message_queue.put(("Processing completed!", 1.0))
            except Exception as e:
                self.logger.error(f"Error during processing: {str(e)}")
                self.message_queue.put((f"Error: {str(e)}", 0.0))
            finally:
                self.processing = False

        threading.Thread(target=process_worker, daemon=True).start()

    def create_import_tab(self):
        with dpg.tab(label="Import Data"):
            with dpg.group():
                dpg.add_text("Transaction Import", color=(41, 120, 182))
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Select Files",
                        callback=lambda: dpg.show_item("file_dialog_tag"),
                        width=120
                    )
                    dpg.add_button(
                        label="Process Files",
                        callback=self.process_files,
                        width=120
                    )
                dpg.add_separator()
                self.log_window = dpg.add_text("", wrap=400)
                self.progress_bar = dpg.add_progress_bar(default_value=0.0, width=400)

    def create_tax_tab(self):
        with dpg.tab(label="Tax Report"):
            with dpg.group():
                dpg.add_text("Generate Tax Report", color=(41, 120, 182))
                with dpg.group():
                    # Tax Year Selection
                    self.tax_year = dpg.add_combo(
                        label="Tax Year",
                        items=self.tax_years,
                        default_value=self.tax_years[0],
                        width=200
                    )

                    # Tax Rules Selection
                    self.tax_rules_combo = dpg.add_combo(
                        label="Tax Rules",
                        items=self.tax_rules,
                        default_value="UK_INDIVIDUAL",
                        width=200
                    )

                    # Report Options
                    with dpg.group():
                        self.audit_only = dpg.add_checkbox(
                            label="Audit Only",
                            tag="audit_only"
                        )
                        self.skip_integrity = dpg.add_checkbox(
                            label="Skip Integrity Check",
                            tag="skip_integrity"
                        )
                        self.summary_only = dpg.add_checkbox(
                            label="Capital Gains Summary Only",
                            tag="summary_only"
                        )
                        self.no_pdf = dpg.add_checkbox(
                            label="No PDF (Terminal Output Only)",
                            tag="no_pdf"
                        )
                        self.export_data = dpg.add_checkbox(
                            label="Export Transaction Records with Price Data",
                            tag="export_data"
                        )

                    # Output Filename
                    dpg.add_input_text(
                        label="Output Filename",
                        default_value="",
                        width=300,
                        tag="output_filename",
                        hint="Leave empty for default filename"
                    )

                    dpg.add_button(
                        label="Generate Report",
                        callback=self.generate_tax_report,
                        width=120
                    )
                dpg.add_separator()
                self.tax_log_window = dpg.add_text("", wrap=400)

    def create_audit_tab(self):
        with dpg.tab(label="Audit"):
            with dpg.group():
                dpg.add_text("Audit Records", color=(41, 120, 182))
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Run Audit",
                        callback=self.run_audit,
                        width=120
                    )
                dpg.add_separator()
                self.audit_log_window = dpg.add_text("", wrap=400)

    def create_international_tab(self):
        with dpg.tab(label="International Settings"):
            with dpg.group():
                dpg.add_text("International Configuration", color=(41, 120, 182))

                # Currency Selection
                self.local_currency = dpg.add_combo(
                    label="Local Currency",
                    items=self.currencies,
                    default_value="GBP",
                    width=200,
                    tag="local_currency"
                )

                # Timezone Selection
                self.local_timezone = dpg.add_combo(
                    label="Local Timezone",
                    items=self.timezones,
                    default_value="Europe/London",
                    width=200,
                    tag="local_timezone"
                )

                # Date Format
                self.date_format = dpg.add_checkbox(
                    label="Date is Day First (DD/MM/YYYY)",
                    default_value=True,
                    tag="date_is_day_first"
                )

                dpg.add_separator()

                # Config Preview
                dpg.add_text("Config Preview:", color=(41, 120, 182))
                self.config_preview = dpg.add_text(
                    "",
                    wrap=400,
                    tag="config_preview"
                )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Save Config",
                        callback=self.save_international_config,
                        width=120
                    )
                    dpg.add_button(
                        label="Load Config",
                        callback=self.load_international_config,
                        width=120
                    )

    def save_international_config(self):
        try:
            config = {
                'local_currency': dpg.get_value("local_currency"),
                'local_timezone': dpg.get_value("local_timezone"),
                'date_is_day_first': dpg.get_value("date_is_day_first")
            }

            config_path = Path.home() / '.bittytax' / 'bittytax.conf'
            config_path.parent.mkdir(exist_ok=True)

            with open(config_path, 'w') as f:
                for key, value in config.items():
                    f.write(f"{key}: '{value}'\n")

            self.update_config_preview()
            self.logger.info("International config saved successfully")
            dpg.set_value("settings_status", "International configuration saved successfully!")

        except Exception as e:
            error_msg = f"Error saving international config: {str(e)}"
            self.logger.error(error_msg)
            dpg.set_value("settings_status", error_msg)

    def load_international_config(self):
        try:
            config_path = Path.home() / '.bittytax' / 'bittytax.conf'

            if not config_path.exists():
                dpg.set_value("settings_status", "No configuration file found. Using defaults.")
                return

            with open(config_path, 'r') as f:
                config_text = f.read()

            # Parse config file
            config = {}
            for line in config_text.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip().strip("'")

            # Update GUI values
            if 'local_currency' in config:
                dpg.set_value("local_currency", config['local_currency'])
            if 'local_timezone' in config:
                dpg.set_value("local_timezone", config['local_timezone'])
            if 'date_is_day_first' in config:
                dpg.set_value("date_is_day_first",
                            config['date_is_day_first'].lower() == 'true')

            self.update_config_preview()
            self.logger.info("International config loaded successfully")
            dpg.set_value("settings_status", "Configuration loaded successfully!")

        except Exception as e:
            error_msg = f"Error loading international config: {str(e)}"
            self.logger.error(error_msg)
            dpg.set_value("settings_status", error_msg)

    def update_config_preview(self):
        config_text = f"""Current Configuration:

    Local Currency: {dpg.get_value("local_currency")}
    Local Timezone: {dpg.get_value("local_timezone")}
    Date Format: {'DD/MM/YYYY' if dpg.get_value("date_is_day_first") else 'MM/DD/YYYY'}
    """
        dpg.set_value("config_preview", config_text)

    def create_international_tab(self):
        with dpg.tab(label="International Settings"):
            with dpg.group():
                dpg.add_text("International Configuration", color=(41, 120, 182))

                # Currency Selection
                self.local_currency = dpg.add_combo(
                    label="Local Currency",
                    items=self.currencies,
                    default_value="GBP",
                    width=200,
                    tag="local_currency"
                )

                # Timezone Selection
                self.local_timezone = dpg.add_combo(
                    label="Local Timezone",
                    items=self.timezones,
                    default_value="Europe/London",
                    width=200,
                    tag="local_timezone"
                )

                # Date Format
                self.date_format = dpg.add_checkbox(
                    label="Date is Day First (DD/MM/YYYY)",
                    default_value=True,
                    tag="date_is_day_first"
                )

                dpg.add_separator()

                # Config Preview
                dpg.add_text("Config Preview:", color=(41, 120, 182))
                self.config_preview = dpg.add_text(
                    "",
                    wrap=400,
                    tag="config_preview"
                )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Save Config",
                        callback=self.save_international_config,
                        width=120
                    )
                    dpg.add_button(
                        label="Load Config",
                        callback=self.load_international_config,
                        width=120
                    )
    def run_bittytax_command(self, command, args=None):
        try:
            # Validate file selection
            if not hasattr(self, 'current_file') or not self.current_file:
                error_msg = "No file selected"
                self.logger.error(error_msg)
                dpg.set_value(self.log_window, error_msg)
                return None

            # Validate file exists
            if not Path(self.current_file).exists():
                error_msg = f"File not found: {self.current_file}"
                self.logger.error(error_msg)
                dpg.set_value(self.log_window, error_msg)
                return None

            # Build command
            cmd = ['bittytax']
            if command:
                cmd.append(command)
            cmd.append(self.current_file)
            if args:
                cmd.extend(args)

            # Set working directory
            output_dir = dpg.get_value("output_dir_input") if hasattr(self, "output_dir_input") else str(os.path.join(os.getcwd(), "reports"))

            # Log and execute command
            self.logger.info(f"Executing command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd=output_dir
            )

            # Handle success
            if result.stdout:
                self.logger.info("Command executed successfully")
                return result.stdout
            return None

        except subprocess.CalledProcessError as e:
            error_msg = f"BittyTax command failed: {e.stderr}"
            self.logger.error(error_msg)
            dpg.set_value(self.log_window, error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error(error_msg)
            dpg.set_value(self.log_window, error_msg)
            raise Exception(error_msg)

    def generate_tax_report(self):
        if not self.current_file:
            dpg.set_value(self.tax_log_window, "Please select a file first")
            return

        self.logger.info("Generating tax report")
        dpg.set_value(self.tax_log_window, "Generating tax report...\n")

        try:
            # Collect user inputs for report generation
            tax_year = dpg.get_value(self.tax_year)
            report_types = dpg.get_value(self.report_types)
            output_dir = dpg.get_value("output_dir_input")
            tax_rules = dpg.get_value(self.tax_rules_combo)

            args = []

            # Tax year
            if tax_year:
                args.extend(['-ty', tax_year.replace('/', '')])

            # Tax rules
            if tax_rules != "UK_INDIVIDUAL":
                args.extend(['--taxrules', tax_rules])

            # Report options
            if dpg.get_value("audit_only"):
                args.append('--audit')
            if dpg.get_value("skip_integrity"):
                args.append('--skipint')
            if dpg.get_value("summary_only"):
                args.append('--summary')
            if dpg.get_value("no_pdf"):
                args.append('--nopdf')
            if dpg.get_value("export_data"):
                args.append('--export')

            # Output filename
            output_filename = dpg.get_value("output_filename")
            if output_filename.strip():
                args.extend(['-o', output_filename])
                output_file = Path(output_dir) / output_filename
            else:
                output_file = Path(output_dir) / f"BittyTax_Report_{tax_year}.pdf"

            # Debug mode
            if dpg.get_value("debug_mode"):
                args.append('--debug')

            # Generate the report using BittyTax command
            output = self.run_bittytax_command(None, args)

            # Display success message
            success_message = f"Report generated successfully!\nLocation: {output_file}"
            if output:
                success_message += f"\n\nOutput:\n{output}"

            dpg.set_value(self.tax_log_window, success_message)
            self.logger.info(f"Report generated at: {output_file}")

            # Automatically extract text from the generated PDF and load it into the chat context
            try:
                import fitz  # PyMuPDF; ensure this is installed via pip install pymupdf

                reports_dir = Path.cwd() / "reports"
                # Find all PDF files in the subdirectory
                pdf_files = list(reports_dir.glob("*.pdf"))
                if pdf_files:
                    # Select the latest PDF based on modification time
                    latest_pdf = max(pdf_files, key=lambda f: f.stat().st_mtime)
                    with fitz.open(str(latest_pdf)) as pdf_doc:
                        extracted_text = ""
                        for page in pdf_doc:
                            extracted_text += page.get_text("text") + "\n"

                    # Load the extracted text into LLM chat context
                    self.load_report_to_chat(extracted_text)
                    self.logger.info(f"Extracted report text loaded from {latest_pdf} into LLM chat context.")
                else:
                    self.logger.warning("No PDF files found in the 'reports' directory.")
            except Exception as e:
                self.logger.error(f"Failed to extract text from PDF: {str(e)}")

            except Exception as e:
                error_msg = f"Failed to extract text from PDF: {str(e)}"
                self.logger.error(error_msg)
                dpg.set_value(self.tax_log_window, error_msg)

        except Exception as e:
            error_msg = f"Error generating report: {str(e)}"
            dpg.set_value(self.tax_log_window, error_msg)
            self.logger.error(error_msg)

    def run_audit(self):
        if not self.current_file:
            dpg.set_value(self.audit_log_window, "Please select a file first")
            return

        self.logger.info("Running audit")
        dpg.set_value(self.audit_log_window, "Running audit...\n")

        try:
            args = ['--audit']
            if dpg.get_value("debug_mode"):
                args.append('--debug')

            output = self.run_bittytax_command(None, args)

            if output:
                dpg.set_value(self.audit_log_window,
                            f"Audit completed successfully!\n\nResults:\n{output}")
                self.logger.info("Audit completed")

        except Exception as e:
            error_msg = f"Error during audit: {str(e)}"
            dpg.set_value(self.audit_log_window, error_msg)
            self.logger.error(error_msg)

    def export_data(self):
        if not self.current_file:
            dpg.set_value(self.log_window, "Please select a file first")
            return

        self.logger.info("Exporting data")
        dpg.set_value(self.log_window, "Exporting data...\n")

        try:
            output_dir = dpg.get_value("output_dir_input")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = Path(output_dir) / f"BittyTax_Export_{timestamp}.csv"

            args = ['--export', '-o', str(output_file)]
            if dpg.get_value("debug_mode"):
                args.append('--debug')

            output = self.run_bittytax_command(None, args)

            if output:
                success_msg = f"Data exported successfully to:\n{output_file}"
                if output:
                    success_msg += f"\n\nOutput:\n{output}"
                dpg.set_value(self.log_window, success_msg)
                self.logger.info(f"Data exported to: {output_file}")

        except Exception as e:
            error_msg = f"Error exporting data: {str(e)}"
            dpg.set_value(self.log_window, error_msg)
            self.logger.error(error_msg)

    def update_ui(self):
        while dpg.is_dearpygui_running():
            try:
                message, progress = self.message_queue.get_nowait()
                dpg.set_value(self.log_window, message)
                dpg.set_value(self.progress_bar, progress)
            except queue.Empty:
                pass
            dpg.render_dearpygui_frame()

    def update_ui(self):
        while dpg.is_dearpygui_running():
            try:
                message, progress = self.message_queue.get_nowait()
                dpg.set_value(self.log_window, message)
                dpg.set_value(self.progress_bar, progress)
            except queue.Empty:
                pass
            dpg.render_dearpygui_frame()

    def create_settings_tab(self):
        with dpg.tab(label="Settings"):
            with dpg.group():
                dpg.add_text("Configuration Settings", color=(41, 120, 182))
                dpg.add_input_text(
                    label="Config Path",
                    default_value="config.json",
                    width=300,
                    tag="config_path_input"
                )
                dpg.add_input_text(
                    label="Output Directory",
                    default_value=str(Path.home()),
                    width=300,
                    tag="output_dir_input"
                )
                dpg.add_checkbox(
                    label="Debug Mode",
                    tag="debug_mode"
                )
                dpg.add_button(
                    label="Save Settings",
                    callback=self.save_settings,
                    width=120
                )
                dpg.add_text("", tag="settings_status", wrap=400)
    def _setup_ai_client(self):
        """Initialize the AI client using the API key from the .env file."""
        load_dotenv()
        if self.ai_service == 'openai':
            import openai  # Ensures the proper module is used
            openai.api_key = os.getenv('OPENAI_API_KEY')
            return openai  # Return the openai module to be used later
        elif self.ai_service == 'gemini':
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            return genai.GenerativeModel('gemini-2.0-pro-exp-02-05')
        else:
            raise ValueError("Invalid AI service")

    def create_llm_chat_tab(self):
        """Create the LLM Chat tab for discussion and recommendations."""
        with dpg.tab(label="LLM Chat"):
            with dpg.group():
                # Make chat log resizable by setting width and height dynamically
                self.chat_log = dpg.add_input_text(
                    multiline=True,
                    height=400,  # Increased height for better readability
                    width=800,   # Increased width
                    readonly=True,
                    tag="chat_log"
                )
            with dpg.group(horizontal=True):
                # Input field for user’s query
                self.chat_input = dpg.add_input_text(
                    label="Your Message",
                    width=700,
                    tag="chat_input"
                )
                dpg.add_button(
                    label="Send",
                    callback=self.send_chat_message,
                    tag="send_button"
                )


    def update_chat_log(self):
        """Refresh the chat log display based on conversation history."""
        chat_content = ""
        for msg in self.chat_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            chat_content += f"[{role}] {content}\n\n"
        dpg.set_value("chat_log", chat_content)

    def send_chat_message(self):
        """Handle sending user's message and start processing the response."""
        user_message = dpg.get_value("chat_input")
        if not user_message.strip():
            return
        self.chat_history.append({"role": "user", "content": user_message})
        self.update_chat_log()
        dpg.set_value("chat_input", "")
        # Process the query on a background thread to keep the GUI responsive
        threading.Thread(
            target=self.process_chat_message,
            args=(user_message,),
            daemon=True
        ).start()

    def process_chat_message(self, user_message: str):
        """Query the LLM service using the current conversation history."""
        try:
            response_text = self.query_llm(self.chat_history)
            if response_text:
                self.chat_history.append({"role": "assistant", "content": response_text})
        except Exception as e:
            self.chat_history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        self.update_chat_log()

    def query_llm(self, messages):
        """Send the conversation history to Gemini and get a response."""
        if self.ai_service == 'gemini':
            # Build a prompt from the conversation history
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

            # Log the prompt for debugging
            self.logger.info(f"Prompt sent to Gemini: {prompt}")

            # Call generate_content with the prompt as a positional argument
            response = self.ai_client.generate_content(prompt)

            # Log the response for debugging
            self.logger.info(f"Response from Gemini: {response.text}")

            return response.text.strip() if response and hasattr(response, 'text') else ""
        else:
            raise ValueError("Invalid AI service")


    def load_report_to_chat(self, report_text: str):
        """Automatically load a report into the chat context for discussion."""
        self.report_text = report_text
        introduction = f"Here is the report context:\n{report_text}\n"
        self.chat_history.append({"role": "system", "content": introduction})
        self.update_chat_log()
    def load_report_to_chat(self, report_text: str):
        """Automatically load a tax report into the chat context."""
        self.report_text = report_text
        introduction = f"Here is the tax report context:\n{report_text}\n"
        # Add the report as a system message in the chat history
        self.chat_history.append({"role": "system", "content": introduction})
        self.update_chat_log()


    def save_settings(self):
        self.logger.info("Saving settings")
        try:
            settings = {
                "config_path": dpg.get_value("config_path_input"),
                "output_dir": dpg.get_value("output_dir_input"),
                "debug_mode": dpg.get_value("debug_mode"),
                "last_used_files": self.selected_files,
                "timestamp": datetime.now().isoformat()
            }

            settings_file = Path("bittytax_gui_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=4)

            message = "Settings saved successfully!"
            self.logger.info("Settings saved")
            dpg.set_value("settings_status", message)

        except Exception as e:
            error_message = f"Error saving settings: {str(e)}"
            self.logger.error(error_message)
            dpg.set_value("settings_status", error_message)

def main():
    app = BittyTaxGUI()
    app.update_ui()

if __name__ == "__main__":
    main()
