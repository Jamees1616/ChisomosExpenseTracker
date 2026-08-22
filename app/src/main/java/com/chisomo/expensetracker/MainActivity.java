package com.chisomo.expensetracker;

import androidx.appcompat.app.AppCompatActivity;

import android.app.AlertDialog;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.util.Locale;

public class MainActivity extends AppCompatActivity {

    private EditText expenseName;
    private EditText expenseAmount;
    private EditText expenseCategory;
    private EditText budgetAmount;

    private TextView totalSpending;
    private TextView budgetText;

    private LinearLayout expenseContainer;

    private SQLiteDatabase database;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        expenseName = findViewById(R.id.expenseName);
        expenseAmount = findViewById(R.id.expenseAmount);
        expenseCategory = findViewById(R.id.expenseCategory);
        budgetAmount = findViewById(R.id.budgetAmount);

        totalSpending = findViewById(R.id.totalSpending);
        budgetText = findViewById(R.id.budgetText);

        expenseContainer = findViewById(R.id.expenseContainer);

        database = openOrCreateDatabase(
                "chisomo_expenses.db",
                MODE_PRIVATE,
                null
        );

        database.execSQL(
                "CREATE TABLE IF NOT EXISTS expenses (" +
                        "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                        "name TEXT NOT NULL," +
                        "amount REAL NOT NULL," +
                        "category TEXT," +
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        );

        database.execSQL(
                "CREATE TABLE IF NOT EXISTS settings (" +
                        "id INTEGER PRIMARY KEY," +
                        "monthly_budget REAL DEFAULT 0)"
        );

        Button saveButton = findViewById(R.id.saveExpenseButton);
        Button saveBudgetButton = findViewById(R.id.saveBudgetButton);

        saveButton.setOnClickListener(v -> saveExpense());
        saveBudgetButton.setOnClickListener(v -> saveBudget());

        loadExpenses();
        loadBudget();
    }

    private void saveExpense() {

        String name = expenseName.getText().toString().trim();
        String amountText = expenseAmount.getText().toString().trim();
        String category = expenseCategory.getText().toString().trim();

        if (name.isEmpty()) {
            expenseName.setError("Enter an expense name");
            return;
        }

        if (amountText.isEmpty()) {
            expenseAmount.setError("Enter an amount");
            return;
        }

        double amount;

        try {
            amount = Double.parseDouble(amountText);
        } catch (NumberFormatException e) {
            expenseAmount.setError("Enter a valid amount");
            return;
        }

        if (amount <= 0) {
            expenseAmount.setError("Amount must be greater than 0");
            return;
        }

        ContentValues values = new ContentValues();
        values.put("name", name);
        values.put("amount", amount);
        values.put("category", category);

        long result = database.insert("expenses", null, values);

        if (result != -1) {

            Toast.makeText(
                    this,
                    "Expense saved successfully",
                    Toast.LENGTH_SHORT
            ).show();

            expenseName.setText("");
            expenseAmount.setText("");
            expenseCategory.setText("");

            loadExpenses();

        } else {

            Toast.makeText(
                    this,
                    "Failed to save expense",
                    Toast.LENGTH_SHORT
            ).show();
        }
    }

    private void loadExpenses() {

        expenseContainer.removeAllViews();

        Cursor cursor = database.rawQuery(
                "SELECT id, name, amount, category " +
                        "FROM expenses ORDER BY id DESC",
                null
        );

        double total = 0;

        if (cursor.getCount() == 0) {

            TextView empty = new TextView(this);
            empty.setText("No expenses yet.");
            empty.setTextSize(16);
            expenseContainer.addView(empty);

            totalSpending.setText("MK 0.00");

            cursor.close();
            updateBudgetDisplay(0);
            return;
        }

        while (cursor.moveToNext()) {

            int id = cursor.getInt(
                    cursor.getColumnIndexOrThrow("id")
            );

            String name = cursor.getString(
                    cursor.getColumnIndexOrThrow("name")
            );

            double amount = cursor.getDouble(
                    cursor.getColumnIndexOrThrow("amount")
            );

            String category = cursor.getString(
                    cursor.getColumnIndexOrThrow("category")
            );

            total += amount;

            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(15, 15, 15, 15);

            TextView details = new TextView(this);

            String text = name +
                    "\nMK " +
                    String.format(Locale.US, "%.2f", amount);

            if (category != null && !category.isEmpty()) {
                text += "\n" + category;
            }

            details.setText(text);
            details.setTextSize(16);

            LinearLayout buttons = new LinearLayout(this);
            buttons.setOrientation(LinearLayout.HORIZONTAL);

            Button edit = new Button(this);
            edit.setText("EDIT");

            Button delete = new Button(this);
            delete.setText("DELETE");

            edit.setOnClickListener(v ->
                    showEditDialog(id, name, amount, category)
            );

            delete.setOnClickListener(v ->
                    confirmDelete(id)
            );

            buttons.addView(edit);
            buttons.addView(delete);

            row.addView(details);
            row.addView(buttons);

            expenseContainer.addView(row);
        }

        cursor.close();

        totalSpending.setText(
                "MK " + String.format(Locale.US, "%.2f", total)
        );

        updateBudgetDisplay(total);
    }

    private void showEditDialog(
            int id,
            String oldName,
            double oldAmount,
            String oldCategory
    ) {

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(30, 10, 30, 10);

        EditText name = new EditText(this);
        name.setHint("Expense name");
        name.setText(oldName);

        EditText amount = new EditText(this);
        amount.setHint("Amount");
        amount.setInputType(2 | 8192);
        amount.setText(String.valueOf(oldAmount));

        EditText category = new EditText(this);
        category.setHint("Category");

        if (oldCategory != null) {
            category.setText(oldCategory);
        }

        layout.addView(name);
        layout.addView(amount);
        layout.addView(category);

        new AlertDialog.Builder(this)
                .setTitle("Edit Expense")
                .setView(layout)
                .setNegativeButton("CANCEL", null)
                .setPositiveButton("SAVE", (dialog, which) -> {

                    String newName = name.getText()
                            .toString()
                            .trim();

                    String amountText = amount.getText()
                            .toString()
                            .trim();

                    String newCategory = category.getText()
                            .toString()
                            .trim();

                    if (newName.isEmpty() || amountText.isEmpty()) {
                        Toast.makeText(
                                this,
                                "Enter valid information",
                                Toast.LENGTH_SHORT
                        ).show();
                        return;
                    }

                    try {

                        double newAmount =
                                Double.parseDouble(amountText);

                        if (newAmount <= 0) {
                            Toast.makeText(
                                    this,
                                    "Amount must be greater than 0",
                                    Toast.LENGTH_SHORT
                            ).show();
                            return;
                        }

                        ContentValues values =
                                new ContentValues();

                        values.put("name", newName);
                        values.put("amount", newAmount);
                        values.put("category", newCategory);

                        database.update(
                                "expenses",
                                values,
                                "id=?",
                                new String[]{
                                        String.valueOf(id)
                                }
                        );

                        Toast.makeText(
                                this,
                                "Expense updated",
                                Toast.LENGTH_SHORT
                        ).show();

                        loadExpenses();

                    } catch (NumberFormatException e) {

                        Toast.makeText(
                                this,
                                "Invalid amount",
                                Toast.LENGTH_SHORT
                        ).show();
                    }
                })
                .show();
    }

    private void confirmDelete(int id) {

        new AlertDialog.Builder(this)
                .setTitle("Delete Expense")
                .setMessage(
                        "Are you sure you want to delete this expense?"
                )
                .setNegativeButton("CANCEL", null)
                .setPositiveButton("DELETE", (dialog, which) -> {

                    database.delete(
                            "expenses",
                            "id=?",
                            new String[]{
                                    String.valueOf(id)
                            }
                    );

                    Toast.makeText(
                            this,
                            "Expense deleted",
                            Toast.LENGTH_SHORT
                    ).show();

                    loadExpenses();
                })
                .show();
    }

    private void saveBudget() {

        String text = budgetAmount.getText()
                .toString()
                .trim();

        if (text.isEmpty()) {
            budgetAmount.setError("Enter a budget");
            return;
        }

        try {

            double budget = Double.parseDouble(text);

            if (budget < 0) {
                budgetAmount.setError(
                        "Budget cannot be negative"
                );
                return;
            }

            database.delete("settings", null, null);

            ContentValues values = new ContentValues();
            values.put("id", 1);
            values.put("monthly_budget", budget);

            database.insert("settings", null, values);

            Toast.makeText(
                    this,
                    "Budget saved",
                    Toast.LENGTH_SHORT
            ).show();

            loadExpenses();

        } catch (NumberFormatException e) {

            budgetAmount.setError("Enter a valid budget");
        }
    }

    private void loadBudget() {

        Cursor cursor = database.rawQuery(
                "SELECT monthly_budget FROM settings WHERE id=1",
                null
        );

        if (cursor.moveToFirst()) {

            double budget = cursor.getDouble(0);

            budgetAmount.setText(
                    String.format(Locale.US, "%.2f", budget)
            );

        }

        cursor.close();

        loadExpenses();
    }

    private void updateBudgetDisplay(double total) {

        Cursor cursor = database.rawQuery(
                "SELECT monthly_budget FROM settings WHERE id=1",
                null
        );

        double budget = 0;

        if (cursor.moveToFirst()) {
            budget = cursor.getDouble(0);
        }

        cursor.close();

        if (budget <= 0) {

            budgetText.setText(
                    "Monthly Budget: Not set"
            );

            return;
        }

        double remaining = budget - total;

        budgetText.setText(
                "Budget: MK " +
                        String.format(Locale.US, "%.2f", budget) +
                        "\nSpent: MK " +
                        String.format(Locale.US, "%.2f", total) +
                        "\nRemaining: MK " +
                        String.format(Locale.US, "%.2f", remaining)
        );
    }

    @Override
    protected void onDestroy() {

        super.onDestroy();

        if (database != null && database.isOpen()) {
            database.close();
        }
    }
}