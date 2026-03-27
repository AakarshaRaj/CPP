class BudgetAnalyzer:

    def calculate_total(self, transactions):
        total = 0
        for t in transactions:
            total += int(t.get('amount', 0))
        return total

    def category_summary(self, transactions):
        summary = {}
        for t in transactions:
            cat = t.get('category', 'Other')
            summary[cat] = summary.get(cat, 0) + int(t.get('amount', 0))
        return summary