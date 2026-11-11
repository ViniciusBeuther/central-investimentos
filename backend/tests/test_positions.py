import unittest
from datetime import date
from decimal import Decimal as D

from app.positions import compute_position


def d(day):
    return date(2024, 1, day)


class PositionTest(unittest.TestCase):
    def test_empty(self):
        p = compute_position([])
        self.assertEqual((p.quantity, p.cost, p.average_price), (0, 0, 0))

    def test_buys_weighted_average(self):
        # 10 @ 10 = 100 and 30 @ 20 = 600 -> 40 shares, cost 700, average 17.50
        p = compute_position([(d(1), "buy", D(10), D(100)), (d(2), "buy", D(30), D(600))])
        self.assertEqual(p.quantity, 40)
        self.assertEqual(p.cost, 700)
        self.assertEqual(p.average_price, D("17.5"))

    def test_partial_sale_keeps_average_and_realizes_profit(self):
        p = compute_position(
            [(d(1), "buy", D(10), D(100)), (d(2), "sell", D(4), D(60))]  # avg 10, sold at 15
        )
        self.assertEqual(p.quantity, 6)
        self.assertEqual(p.average_price, 10)  # unchanged by the sale
        self.assertEqual(p.cost, 60)
        self.assertEqual(p.realized_profit, 20)  # 60 - 4 x 10

    def test_full_sale_zeroes_position(self):
        p = compute_position([(d(1), "buy", D(5), D(50)), (d(2), "sell", D(5), D(40))])
        self.assertEqual((p.quantity, p.cost), (0, 0))
        self.assertEqual(p.realized_profit, -10)

    def test_fractional_quantity(self):
        p = compute_position([(d(1), "buy", D("0.11"), D("472.24"))])
        self.assertEqual(p.quantity, D("0.11"))

    def test_same_day_buy_counts_before_sell(self):
        # listed sell first, but the buy of the same day happens first
        p = compute_position([(d(1), "sell", D(5), D(60)), (d(1), "buy", D(10), D(100))])
        self.assertEqual(p.quantity, 5)
        self.assertEqual(p.warnings, [])

    def test_oversell_warns_and_never_goes_negative(self):
        p = compute_position([(d(1), "buy", D(2), D(20)), (d(2), "sell", D(5), D(50))])
        self.assertEqual(p.quantity, 0)
        self.assertEqual(len(p.warnings), 1)

    def test_split_keeps_cost_and_divides_average(self):
        # CPTS11 style: 3 shares bought, 10:1 split = +27 extra, then 30 sold
        p = compute_position([(d(1), "buy", D(3), D(30))], [(d(2), "split", D(27), None, None)])
        self.assertEqual((p.quantity, p.cost, p.average_price), (30, 30, 1))
        p = compute_position(
            [(d(1), "buy", D(3), D(30)), (d(3), "sell", D(30), D(33))], [(d(2), "split", D(27), None, None)]
        )
        self.assertEqual((p.quantity, p.realized_profit, p.warnings), (0, 3, []))

    def test_action_takes_effect_before_trades_of_the_same_day(self):
        # split and a sale of the new units on the same day: the split comes first
        p = compute_position(
            [(d(1), "buy", D(3), D(30)), (d(2), "sell", D(30), D(33))], [(d(2), "split", D(27), None, None)]
        )
        self.assertEqual((p.quantity, p.warnings), (0, []))

    def test_reverse_split_with_fraction_auction(self):
        # AMER3 style: 54 shares (cost 60.48), 100:1 -> 0.54, fraction sold for 3.58
        p = compute_position(
            [(d(1), "buy", D(54), D("60.48"))],
            [(d(2), "reverse_split", D("0.54"), None, None), (d(3), "fraction", D("0.54"), None, D("3.58"))],
        )
        self.assertEqual((p.quantity, p.cost), (0, 0))
        self.assertEqual(p.realized_profit, D("3.58") - D("60.48"))

    def test_bonus_with_unknown_cost_warns_and_lowers_average(self):
        p = compute_position([(d(1), "buy", D(28), D(280))], [(d(2), "bonus", D("2.8"), None, None)])
        self.assertEqual(p.quantity, D("30.8"))
        self.assertEqual(p.cost, 280)
        self.assertEqual(len(p.warnings), 1)

    def test_bonus_with_declared_cost_adds_cost(self):
        p = compute_position([(d(1), "buy", D(10), D(100))], [(d(2), "bonus", D(2), D(5), None)])
        self.assertEqual((p.quantity, p.cost), (12, 110))
        self.assertEqual(p.warnings, [])

    def test_bonus_fraction_leaves_whole_shares(self):
        # TASA4 style: bonus 2.80, fraction 0.80 sold for 5.40 -> 2 whole shares stay
        p = compute_position(
            [(d(1), "buy", D(28), D(280))],
            [(d(2), "bonus", D("2.8"), D(0), None), (d(3), "fraction", D("0.8"), None, D("5.4"))],
        )
        self.assertEqual(p.quantity, 30)

    def test_transfer_moves_quantity_and_cost(self):
        out = compute_position([(d(1), "buy", D(10), D(100))], [(d(2), "transfer_out", D(4), D(10), None)])
        self.assertEqual((out.quantity, out.cost, out.warnings), (6, 60, []))
        into = compute_position([], [(d(2), "transfer_in", D(4), D(10), None)])
        self.assertEqual((into.quantity, into.cost, into.warnings), (4, 40, []))

    def test_klbn_style_bonus_unbundled_and_fraction_sold(self):
        # KLBN4: 2.8 received by transfer, 0.8 fraction sold at auction, 2 whole shares stay
        p = compute_position(
            [], [(d(1), "transfer_in", D("2.8"), None, None), (d(2), "fraction", D("0.8"), None, D("3.47"))]
        )
        self.assertEqual(p.quantity, 2)
        self.assertEqual(p.realized_profit, D("3.47"))

    def test_unknown_kind_fails(self):
        with self.assertRaises(ValueError):
            compute_position([(d(1), "gift", D(1), D(1))])


if __name__ == "__main__":
    unittest.main()
