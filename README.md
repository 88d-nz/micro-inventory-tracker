# Micro Inventory Tracker

A simple, lightweight inventory management system for small producers who need to track raw materials and production without the complexity and cost of enterprise ERP systems. Built with Python/Flask and SQLite.

## Features

- **Product Groups** - Organize your inventory (e.g., Candles, Yule Folk, Decorations)
- **Raw Materials Tracking** - Track quantities, units, and costs
- **Finished Goods Management** - Track inventory levels with SKUs
- **BOMs (Bill of Materials)** - Create recipes with raw materials + labor costs
- **Production Recording** - Produce finished goods and automatically deduct raw materials
- **Stock Adjustments** - Manual adjustments + full history log
- **CSV Export** - Export all data to CSV files

## Quick Start

### Prerequisites
- Python 3.7+
- pip (Python package installer)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/88d-nz/micro-inventory-tracker.git
   cd micro-inventory-tracker
   ```

2. Create a virtual environment (optional but recommended):
   ```bash
   python3 -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your web browser and go to:
   ```
   http://localhost:5000
   ```

The application will automatically create a SQLite database file (`inventory.db`) on first run.

## Usage Guide

### 1. Create Product Groups
Navigate to **Product Groups** and create categories for your products (e.g., "Candles", "Yule Folk", "Decorations").

### 2. Add Raw Materials
Go to **Raw Materials** and add your ingredients/components:
- Name (e.g., "Soy Wax")
- Unit (e.g., "kg", "pcs", "ml")
- Starting Quantity
- Cost per Unit
- Assign to a Group

### 3. Add Finished Goods
Go to **Finished Goods** and add your products:
- Name (e.g., "Soy Candle - Lavender")
- SKU (Stock Keeping Unit)
- Assign to a Group

### 4. Create BOMs
For each finished good, create a **BOM** (recipe):
- Select the finished good
- Add raw material requirements (quantity per unit)
- Add labor costs if applicable

### 5. Record Production
When you produce items:
1. Go to **Production**
2. Select the product and BOM
3. Enter the quantity produced
4. Click "Record Production"

The system will:
- Increase your finished goods quantity
- Automatically deduct the required raw materials
- Log the transaction in Stock Adjustments

### 6. Manual Adjustments
If you need to manually adjust stock levels:
- Use the edit buttons on the Raw Materials or Finished Goods pages
- All changes are logged in Stock Adjustments

### 7. Export Data
Use the **Export Data** section to download CSV files of:
- Raw Materials
- Finished Goods
- BOMs
- Production Records

## File Structure

```
micro-inventory-tracker/
├── app.py              # Main application
├── run.sh              # Linux/macOS startup script
├── requirements.txt    # Python dependencies
├── inventory.db        # SQLite database (auto-created)
└── README.md           # This file
```

## Technical Details

- **Backend**: Python 3 with Flask
- **Database**: SQLite (no external database server required)
- **Frontend**: Bootstrap 5.1.3, Font Awesome icons
- **Deployment**: Runs locally on any machine with Python 3.7+

## Tips

- Regularly export your data as CSV backups
- Use Product Groups to organize materials by product line
- Check the Dashboard for low stock alerts
- All stock movements are logged in the Stock Adjustments page
- BOMs support multiple versions - create new versions as recipes evolve

## License

MIT License

## Support

If you encounter any issues:
1. Check that Python 3.7+ is installed
2. Verify all dependencies are installed (`pip install -r requirements.txt`)
3. Check that port 5000 is not already in use

