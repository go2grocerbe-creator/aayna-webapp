# From the founder kit (21 Oct 2026), unchanged except the import path.
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gallery_contract import *

class TestGallery(unittest.TestCase):
    def setUp(self):
        self.urls=['/product-images/ring/a-1200.webp','/product-images/ring/b-1200.webp']
        self.gallery=normalize_legacy(self.urls)
    def test_legacy_order_and_cover(self):
        self.assertEqual(image_cover(self.gallery),self.urls[0]);self.assertEqual(self.gallery[1]['position'],1)
    def test_reorder_cover(self):
        g=apply_order(self.gallery,[self.gallery[1]['id'],self.gallery[0]['id']]);self.assertEqual(image_cover(g),self.urls[1])
    def test_stable_ids(self):self.assertEqual(normalize_legacy(self.urls),self.gallery)
    def test_missing_id_rejected(self):
        with self.assertRaises(GalleryError):apply_order(self.gallery,[self.gallery[0]['id']])
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(GalleryError):apply_order(self.gallery,[self.gallery[0]['id']]*2)
    def test_host_allowlist(self):
        self.assertFalse(valid_url('https://evil.example/a.webp'))
        self.assertTrue(valid_url('https://images.shopaayna.com/a.webp',('images.shopaayna.com',)))
        self.assertFalse(valid_url('http://images.shopaayna.com/a.webp',('images.shopaayna.com',)))
    def test_directory_escape(self):self.assertFalse(valid_url('/product-images/../../private'))
    def test_duplicates_rejected(self):
        with self.assertRaises(GalleryError):validate_gallery(self.gallery+self.gallery[:1])
    def test_empty_allowed(self):self.assertIsNone(image_cover([]))
    def test_alt_markup_refused(self):
        g=[dict(self.gallery[0],alt='<script>')]
        with self.assertRaises(GalleryError):validate_gallery(g)

if __name__=='__main__':unittest.main()
