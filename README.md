# BittyTax GUI

A modern graphical user interface for BittyTax - the UK Cryptoasset Tax Calculator. This GUI provides an intuitive and simple interface for managing your crypto tax calculations.

## ⭐ Features
- 🎨 Modern, user-friendly interface
- 📝 Comprehensive logging
- 🌍 International currency support
- 📄 PDF report generation through the GUI
- 💼 Support for all BittyTax features

## 🙏 Credits
This GUI is built on top of [BittyTax](https://github.com/BittyTax/BittyTax), the original command-line crypto tax calculator. All tax calculation logic and core functionality is from the original BittyTax project.

## ⚙️ Requirements
- Python 3.11.11 (tested successfully in this version of Python)
- BittyTax installation 
```bash
pip install bittytax
```
- Navigate to `bitty_tax_gui` subdir:
```bash
cd bitty_tax_gui
```
- Required packages:
```bash
pip install -r requirements.txt
```

## 🚀 Installation
1. Clone this repository
2. Create a virtual environment:
```bash
python -m venv bitty
source bitty/bin/activate  # On Windows: bitty\Scripts\activate
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## 📖 Usage
1. Launch the GUI:
```bash
python bitty_tax_gui.py
```

2. Navigate through the tabs:
- 📥 Import Data: Select and process transaction files
- 📊 Tax Report: Generate tax calculations
- 🔍 Audit: Review wallet balances
- 🌍 International Settings: Configure currency and timezone preferences
- ⚠️ No 1: With currencies other than British pound you can create the pdf report but the inside GUI (No PDF) report has errors
- ⚠️ No 2: You will find produced PDFs and CSVs in `reports` folder and the logs in `logs` folder.

## 💝 Support Development
If you find this tool helpful, consider supporting development through crypto donations:

**Solana (SOL)**  
`BEDzMx27TPRh6d1tJokGuSLec4yut7KJaw1QoZRJw7bH`

**Ethereum (ETH)**  
`0x530B73D02793b5bB12C7571A053c81883cE078FD`

**Polygon**  
`0x530B73D02793b5bB12C7571A053c81883cE078FD`

**Bitcoin (BTC)**  
`bc1qjq8rmvkvautk2t9urm739vuw3gn00zd5l9qmqd`

## ⚠️ Disclaimer
- This software is provided 'as is' without any warranties or guarantees.
- I bear NO responsibility for any errors, inaccuracies, or issues arising from the use of this software.
- This is NOT financial advice and should not be treated as such.
- Always verify calculations and consult with a qualified tax professional before making any tax-related decisions.
- Users are solely responsible for verifying the accuracy of all calculations and ensuring compliance with their local tax regulations.
- The software should be used as a tool to assist with calculations only and not as definitive tax advice.

## 📜 License
This project follows the same license as the original BittyTax project. See the [BittyTax](https://github.com/BittyTax/BittyTax) repository for full license details.

---
Made with ❤️ for the crypto community
