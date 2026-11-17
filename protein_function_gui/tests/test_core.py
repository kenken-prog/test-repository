import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import read_sequences, tokenize, predict, csv_bytes
from gensim.models.doc2vec import Doc2Vec, TaggedDocument


class PipelineTests(unittest.TestCase):
    def test_formats_and_invalid_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'input'
            p.write_text('>p1\nACD\nEFG\n>p2\nMKT\n')
            self.assertEqual(read_sequences(p), [('p1', 'ACDEFG'), ('p2', 'MKT')])
            p.write_text('id,sequence\np1,ACDEFG\n')
            self.assertEqual(read_sequences(p), [('p1', 'ACDEFG')])
            p.write_text('id,sequence\np1,ACD\np1,MKT\n')
            with self.assertRaises(ValueError):
                read_sequences(p)

    def test_split_examples(self):
        self.assertEqual(tokenize('ACDEFGH', 3, True), ['ACD', 'CDE', 'DEF', 'EFG', 'FGH'])
        self.assertEqual(tokenize('ACDEFGH', 3, False), ['ACD', 'EFG', 'FGH'])
        self.assertEqual(tokenize('ACDEFG', 3, False), ['ACD', 'EFG'])
        self.assertEqual(tokenize('AC', 3, True), [])
        self.assertEqual(tokenize('AC', 3, False), [])

    def test_model_round_trip_and_rejections(self):
        model = Doc2Vec([TaggedDocument(tokenize('ACDEFGACDEFG', 3, True), ['COG_TEST_A']),
                         TaggedDocument(tokenize('MKTWMKTWMKTW', 3, True), ['COG_TEST_B'])],
                        min_count=1, vector_size=12, epochs=30, workers=1, seed=42, dm=0)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'test.model'
            model.save(str(p))
            model = Doc2Vec.load(str(p))
            rows = predict(model, [('valid', 'ACDEFG'), ('short', 'AC'), ('bad', 'AC*'), ('oov', 'YYY')])
            self.assertEqual([r['status'] for r in rows], ['ok', 'error', 'error', 'unassigned'])
            self.assertIn(rows[0]['predicted_function_id'], ['COG_TEST_A', 'COG_TEST_B'])
            self.assertAlmostEqual(rows[0]['cosine_similarity'], predict(model, [('valid', 'ACDEFG')])[0]['cosine_similarity'])
            self.assertTrue(csv_bytes(rows).startswith(b'\xef\xbb\xbf'))


if __name__ == '__main__':
    unittest.main()
