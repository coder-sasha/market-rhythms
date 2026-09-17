"""
2026-09-09
Offline regression checks for seasonal windows, figures, and app integration.
"""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from seasonal_analysis import (
    calculate_sell_in_may, calculate_september, calculate_santa,
    decompose_prices, decomposition_chart, chart_title,
)

ROOT = Path(__file__).resolve().parents[1]


class SeasonalTests(unittest.TestCase):
    def test_month_windows(self) -> None:
        dates = pd.date_range('2020-12-31', periods=13, freq='ME')  # big improvement: it is 'ME' now not 'M'  
        data = pd.DataFrame({'Close': 100 * 1.01 ** np.arange(13)}, index=dates)
        curves = calculate_sell_in_may(data)
        self.assertAlmostEqual(curves.iloc[-1, 0], 1000 * 1.01 ** 6)
        self.assertAlmostEqual(curves.iloc[-1, 1], 1000 * 1.01 ** 6)
        self.assertAlmostEqual(curves.iloc[-1, 2], 1000 * 1.01 ** 12)
        september = calculate_september(data)
        self.assertAlmostEqual(september.iloc[-1, 0], 1000 * 1.01 ** 11)

    def test_missing_month_does_not_bridge(self) -> None:
        data = pd.DataFrame({'Close': [100, 200, 220]},
                            index=pd.to_datetime(['2020-01-31', '2020-03-31', '2020-04-30']))
                            
        self.assertAlmostEqual(calculate_september(data).iloc[-1, 1], 1100)

    def test_santa_window_and_empty(self) -> None:
        dates = pd.bdate_range('2020-12-01', '2021-01-15')
        data = pd.DataFrame({'Close': np.arange(len(dates)) + 100.0}, index=dates)
        december = data.loc['2020-12', 'Close']
        january = data.loc['2021-01', 'Close']
        result = calculate_santa(data)
        self.assertEqual(result['Year'].tolist(), [2020])
        self.assertAlmostEqual(result.iloc[0]['Return_Pct'], (january.iloc[1] / december.iloc[-5] - 1) * 100)
        self.assertTrue(calculate_santa(data.loc['2020']).empty)

    def test_decomposition_title_and_short_history(self) -> None:
        dates = pd.date_range('2019-01-31', periods=60, freq='ME')
        data = pd.DataFrame({'Close': np.arange(60) + 100.0}, index=dates)
        prices, decomposition = decompose_prices(data)
        title = chart_title('DIA', 'Time Series Decomposition', dates[0], dates[-1])
        figure = decomposition_chart(prices, decomposition, title)
        self.assertEqual(len(figure.data), 4)
        self.assertEqual(figure.layout.title.text, 'DIA Time Series Decomposition (2019 - 2023)')
        with self.assertRaisesRegex(ValueError, '42 monthly'):
            decompose_prices(data.iloc[:20])

    def test_scripts_import_without_download_or_browser(self) -> None:
        with patch('yfinance.download', side_effect=AssertionError('unexpected download')):
            for filename in ['ts-test.py', 'win-sum-test.py', 'santa-test.py', 'september-test.py']:
                spec = importlib.util.spec_from_file_location(filename, ROOT / filename)
                spec.loader.exec_module(importlib.util.module_from_spec(spec))

    def test_streamlit_tabs_offline(self) -> None:
        dates = pd.bdate_range('2016-12-01', '2026-09-16')
        data = pd.DataFrame({'Close': 100 + np.arange(len(dates)) * .03
                            + np.sin(np.arange(len(dates)) / 20)}, index=dates)
                            
        with patch('yfinance.download', return_value=data):
            app = AppTest.from_file(str(ROOT / 'st-returns-hm.py')).run(timeout=90)
            
        self.assertEqual(len(app.exception), 0, str(app.exception))
        self.assertEqual(len(app.error), 0, str(app.error))
        labels = [tab.label for tab in app.tabs]
        for name in ['Time Series Decomposition', 'Sell in May', 'Santa Rally', 'Weak Septemebr']:
            self.assertEqual(labels.count(name), 6)
            
        self.assertEqual(len(app.get('plotly_chart')), 24)

# ???