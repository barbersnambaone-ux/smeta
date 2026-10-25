import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from petrovich_adapter import validate_url,extract_candidates,history_row
class AdapterTests(unittest.TestCase):
    def test_safe_url(self):
        self.assertTrue(validate_url('https://moscow.petrovich.ru/product/123456/'))
        for url in ('http://moscow.petrovich.ru/product/123456/', 'https://evil.com/product/123/', 'https://petrovich.ru.evil.com/product/123/'):
            with self.assertRaises(ValueError): validate_url(url)
    def test_extract_candidates(self):
        result=extract_candidates('Код: 106958 Цена 577 ₽ за шт. С картой 550 ₽')
        self.assertIn(577,result['prices']);self.assertIn('106958',result['skus'])
    def test_history(self):
        r=history_row('106958','Тестовый товар',577,'https://moscow.petrovich.ru/product/106958/','Инженер')
        self.assertEqual(r['Регион'],'Москва')
        self.assertEqual(r['Цена упаковки'],577)
if __name__=='__main__':unittest.main()
