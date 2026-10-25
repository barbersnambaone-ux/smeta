import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import read_table,calculate
ROOT=Path(__file__).resolve().parents[1]/'sample_data'
class TestEngine(unittest.TestCase):
    def test_quantity_and_no_fake_price(self):
        data=[read_table(None,ROOT/x) for x in ('volumes.csv','manufacturer_norms.csv','petrovich_prices.csv','labor.csv')]
        mats,works,issues,total=calculate(*data,{('plaster-10','DEMO-SKU')})
        self.assertEqual(int(mats.iloc[0]['Упаковок']),54)
        self.assertFalse(total['Полнота данных'])
        self.assertTrue(any('неверная цена' in x for x in issues))
    def test_missing_approval(self):
        data=[read_table(None,ROOT/x) for x in ('volumes.csv','manufacturer_norms.csv','petrovich_prices.csv','labor.csv')]
        mats,works,issues,total=calculate(*data,set())
        self.assertFalse(bool(mats.iloc[0]['Подтверждено']))
        self.assertTrue(any('не подтверждено' in x for x in issues))
if __name__=='__main__': unittest.main()
