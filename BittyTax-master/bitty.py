import dearpygui.dearpygui as dpg
from pathlib import Path
import threading
import queue
from datetime import datetime
import json
import sys
import logging

# BittyTax core imports
from bittytax import tax
from config import Config
from constants import *
from import_records import ImportRecords
from export_records import export_records
from report import ReportGenerator
from audit import AuditRecords
from holdings import Holdings
from exceptions import DataError, OptionsError
from t_record import TransactionRecord
from price.valuations import ValueManager

class BittyTaxGUI:
    def __init__(self):
        # Initialize core components
        self.config = Config()
        self.value_manager = ValueManager()
        self.records = []
        self.holdings = None
        self.tax_report = None
        self.audit_results = None

        # GUI state management
        self.message_queue = queue.Queue()
        self.processing = False

        # Setup logging
        self.setup_logging()

        # Initialize GUI
        dpg.create_context()
        dpg.create_viewport(title="BittyTax Manager", width=1280, height=800)
        dpg.set_viewport_vsync(True)

        self.setup_theme()
        self.create_main_window()

        dpg.setup_dearpygui()
        dpg.show_viewport()

    def setup_logging(self):
        self.logger = logging.getLogger('BittyTaxGUI')
        self.logger.setLevel(logging.INFO)

        # File handler
        fh = logging.FileHandler('bittytax_gui.log')
        fh.setLevel(logging.INFO)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def setup_theme(self):
        with dpg.theme() as self.main_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (25, 25, 25))
                dpg.add_theme_color(dpg.mvThemeCol_Button, (52, 140, 215))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (72, 160, 235))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 5)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5)
        dpg.bind_theme(self.main_theme)

    def create_main_window(self):
        with dpg.window(label="BittyTax Manager", width=1280, height=800) as self.main_window:
            with dpg.tab_bar():
                self.create_import_tab()
                self.create_holdings_tab()
                self.create_tax_tab()
                self.create_audit_tab()
                self.create_report_tab()
                self.create_settings_tab()

    def create_import_tab(self):
        with dpg.tab(label="Import Data"):
            with dpg.group():
                dpg.add_text("Transaction Import")

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Select Files",
                        callback=self.select_import_files,
                        width=120
                    )
                    self.import_files_list = dpg.add_listbox(
                        label="Selected Files",
                        items=[],
                        width=400,
                        num_items=5
                    )

                dpg.add_separator()

                with dpg.group():
                    self.import_type = dpg.add_combo(
                        label="Import Type",
                        items=list(IMPORT_FORMATS.keys()),
                        default_value=list(IMPORT_FORMATS.keys())[0],
                        width=200
                    )

                    self.exchange = dpg.add_combo(
                        label="Exchange",
                        items=list(EXCHANGES),
                        default_value=list(EXCHANGES)[0],
                        width=200
                    )

                dpg.add_button(
                    label="Import Transactions",
                    callback=self.import_transactions,
                    width=200
                )

                dpg.add_separator()

                with dpg.group():
                    dpg.add_text("Import Status")
                    self.import_progress = dpg.add_progress_bar(
                        default_value=0.0,
                        width=400
                    )
                    self.import_status = dpg.add_text("")

    def create_holdings_tab(self):
        with dpg.tab(label="Holdings"):
            with dpg.group():
                dpg.add_text("Current Holdings")

                self.holdings_table = dpg.add_table(
                    header_row=True,
                    resizable=True,
                    policy=dpg.mvTable_SizingStretchProp
                )

                dpg.add_table_column(label="Asset")
                dpg.add_table_column(label="Amount")
                dpg.add_table_column(label="Value (Local)")
                dpg.add_table_column(label="Cost Basis")
                dpg.add_table_column(label="Unrealized P/L")

                dpg.add_button(
                    label="Refresh Holdings",
                    callback=self.update_holdings,
                    width=200
                )
    def create_tax_tab(self):
        with dpg.tab(label="Tax Calculations"):
            with dpg.group():
                dpg.add_text("Tax Year Settings")
                self.selected_tax_year = dpg.add_combo(
                    label="Tax Year",
                    items=self._get_tax_years(),
                    default_value=str(datetime.now().year)
                )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Calculate Tax",
                        callback=self.calculate_tax,
                        width=150
                    )
                    dpg.add_button(
                        label="Generate PDF Report",
                        callback=self.generate_tax_report,
                        width=150
                    )

            dpg.add_separator()

            with dpg.child_window(height=400):
                with dpg.tab_bar():
                    with dpg.tab(label="Capital Gains"):
                        self.gains_table = dpg.add_table(
                            header_row=True,
                            resizable=True,
                            policy=dpg.mvTable_SizingStretchProp
                        )
                        dpg.add_table_column(label="Date")
                        dpg.add_table_column(label="Asset")
                        dpg.add_table_column(label="Quantity")
                        dpg.add_table_column(label="Proceeds")
                        dpg.add_table_column(label="Cost")
                        dpg.add_table_column(label="Gain/Loss")
                        dpg.add_table_column(label="Type")

                    with dpg.tab(label="Income"):
                        self.income_table = dpg.add_table(
                            header_row=True,
                            resizable=True,
                            policy=dpg.mvTable_SizingStretchProp
                        )
                        dpg.add_table_column(label="Date")
                        dpg.add_table_column(label="Type")
                        dpg.add_table_column(label="Asset")
                        dpg.add_table_column(label="Amount")
                        dpg.add_table_column(label="Value (GBP)")

    def create_audit_tab(self):
        with dpg.tab(label="Audit"):
            with dpg.group():
                dpg.add_text("Wallet Balances")

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Run Audit",
                        callback=self.run_audit,
                        width=150
                    )
                    dpg.add_button(
                        label="Export Audit Report",
                        callback=self.export_audit,
                        width=150
                    )

            dpg.add_separator()

            self.audit_table = dpg.add_table(
                header_row=True,
                resizable=True,
                policy=dpg.mvTable_SizingStretchProp
            )
            dpg.add_table_column(label="Wallet")
            dpg.add_table_column(label="Asset")
            dpg.add_table_column(label="Balance")
            dpg.add_table_column(label="Value (GBP)")
            dpg.add_table_column(label="Status")

    def calculate_tax(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._calculate_tax_thread, daemon=True).start()
        threading.Thread(target=self._update_gui, daemon=True).start()

    def _calculate_tax_thread(self):
        try:
            from tax import TaxCalculator
            from import_records import ImportRecords

            tax_year = int(dpg.get_value(self.selected_tax_year))

            # Import and validate records
            importer = ImportRecords()
            self.records = importer.import_file(self.current_file)

            # Calculate tax
            calculator = TaxCalculator(self.records)
            self.tax_report = calculator.process(tax_year=tax_year)

            # Update tables with results
            self._update_tax_tables()

            self.message_queue.put(("Tax calculations completed successfully", 1.0))

        except Exception as e:
            self.message_queue.put((f"Error calculating tax: {str(e)}", 0))
        finally:
            self.processing = False

    def run_audit(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._run_audit_thread, daemon=True).start()
        threading.Thread(target=self._update_gui, daemon=True).start()

    def _run_audit_thread(self):
        try:
            from audit import AuditRecords

            auditor = AuditRecords(self.records)
            self.audit_results = auditor.audit()

            self._update_audit_table()

            self.message_queue.put(("Audit completed successfully", 1.0))

        except Exception as e:
            self.message_queue.put((f"Error running audit: {str(e)}", 0))
        finally:
            self.processing = False

    def create_report_tab(self):
        with dpg.tab(label="Reports"):
            with dpg.group():
                dpg.add_text("Report Generation")

                self.report_type = dpg.add_combo(
                    label="Report Type",
                    items=["Full Tax Report", "Audit Report", "Capital Gains Summary"],
                    default_value="Full Tax Report"
                )

                self.tax_year = dpg.add_input_int(
                    label="Tax Year",
                    default_value=datetime.now().year,
                    min_value=2013,
                    max_value=datetime.now().year
                )

                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Generate PDF Report",
                        callback=self.generate_report,
                        width=200
                    )
                    dpg.add_button(
                        label="Export to Excel",
                        callback=self.export_to_excel,
                        width=200
                    )

            dpg.add_separator()

            with dpg.child_window(height=400):
                self.report_log = dpg.add_text("Report Log:")

    def generate_report(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._generate_report_thread, daemon=True).start()
        threading.Thread(target=self._update_gui, daemon=True).start()

    def _generate_report_thread(self):
        try:
            from report import ReportGenerator

            report_type = dpg.get_value(self.report_type)
            tax_year = dpg.get_value(self.tax_year)

            generator = ReportGenerator(
                self.tax_report,
                self.config,
                tax_year=tax_year,
                report_type=report_type
            )

            output_file = f"BittyTax_Report_{tax_year}.pdf"
            generator.generate_pdf(output_file)

            self.message_queue.put((f"Report generated: {output_file}", 1.0))

        except Exception as e:
            self.message_queue.put((f"Error generating report: {str(e)}", 0))
        finally:
            self.processing = False

    def export_to_excel(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._export_excel_thread, daemon=True).start()
        threading.Thread(target=self._update_gui, daemon=True).start()

    def _export_excel_thread(self):
        try:
            from export_records import export_records

            output_file = f"BittyTax_Export_{datetime.now().strftime('%Y%m%d')}.xlsx"
            export_records(self.records, output_file)

            self.message_queue.put((f"Data exported to: {output_file}", 1.0))

        except Exception as e:
            self.message_queue.put((f"Error exporting data: {str(e)}", 0))
        finally:
            self.processing = False

    def _update_gui(self):
        while self.processing or not self.message_queue.empty():
            try:
                message, progress = self.message_queue.get_nowait()

                # Update progress bar if exists
                if hasattr(self, 'progress_bar'):
                    dpg.set_value(self.progress_bar, progress)

                # Update log window
                current_log = dpg.get_value(self.log_window)
                timestamp = datetime.now().strftime('%H:%M:%S')
                dpg.set_value(
                    self.log_window,
                    f"{current_log}\n[{timestamp}] {message}"
                )

            except queue.Empty:
                continue
            threading.Event().wait(0.1)

    def run_audit(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._run_audit_thread, daemon=True).start()
        threading.Thread(target=self._update_gui, daemon=True).start()

    def _run_audit_thread(self):
        try:
            from audit import AuditRecords

            auditor = AuditRecords(self.records)
            self.audit_results = auditor.audit()

            # Update audit display
            self._update_audit_table()

            self.message_queue.put(("Audit completed successfully", 1.0))

        except Exception as e:
            self.message_queue.put((f"Error during audit: {str(e)}", 0))
        finally:
            self.processing = False

    def _update_audit_table(self):
        if not hasattr(self, 'audit_table'):
            return

        dpg.delete_item(self.audit_table, children_only=True)

        if not self.audit_results:
            return

        for wallet, assets in self.audit_results.items():
            for asset, balance in assets.items():
                with dpg.table_row(parent=self.audit_table):
                    dpg.add_text(wallet)
                    dpg.add_text(asset)
                    dpg.add_text(f"{balance:,.8f}")
                    dpg.add_text(self._get_asset_value(asset, balance))

    def run(self):
        dpg.setup_dearpygui()
        dpg.show_viewport()
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

if __name__ == "__main__":
    app = BittyTaxGUI()
    app.run()
