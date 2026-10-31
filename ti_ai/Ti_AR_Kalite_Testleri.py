import unittest
import numpy as np
from unittest import mock
from ti_ar_render import _earth_texture,draw_object,apply_face_mask,_mask_sprite
from ti_ar_core import Point
class ArtTests(unittest.TestCase):
    def test_nasa_texture_available(self):
        t=_earth_texture()
        self.assertIsNotNone(t)
        self.assertGreater(t.shape[1],1024)
    def test_globe_renders(self):
        im=np.zeros((280,320,3),np.uint8)
        draw_object(im,(160,140),80,'3D Dünya',.3)
        self.assertGreater(int(im.sum()),100000)
    def test_globe_fallback(self):
        im=np.zeros((280,320,3),np.uint8)
        with mock.patch('ti_ar_render._earth_texture',return_value=None):draw_object(im,(160,140),80,'3D Dünya',.3)
        self.assertGreater(int(im.sum()),10000)
    def test_antialias_alpha(self):
        from ti_ar_render import _sphere_rgba
        a=_sphere_rgba('3D Dünya',80,.6)[:,:,3]
        self.assertGreater(int(((a>0)&(a<255)).sum()),0)
    def test_all_masks(self):
        for style in ['Muzip yüz (özgün)','Gözlük','Bıyık','Şapka','Emoji','Korku']:
            mask=_mask_sprite(style,480)
            self.assertEqual(mask.shape,(480,480,4))
    def test_no_face_safe(self):
        im=np.zeros((120,120,3),np.uint8)
        self.assertEqual(int(apply_face_mask(im,[], 'Gözlük').sum()),0)

if __name__=='__main__':unittest.main()
