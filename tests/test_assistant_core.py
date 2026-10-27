import unittest
from datetime import datetime
from unittest.mock import Mock
from requests.exceptions import Timeout
from c301_monitor.assistant_core import answer_question, get_weather, conditions

class WeatherTests(unittest.TestCase):
    def test_weather_with_mocked_api(self):
        geocode = Mock()
        geocode.json.return_value = {"results": [
            {"name":"Ankara", "latitude": 39.93, "longitude":32.86, "country_code":"TR"}]}
        weather = Mock()
        weather.json.return_value = {"current":{
            "temperature_2m":12.4,"apparent_temperature":10.0,"weather_code":3,"wind_speed_10m":15}}
        session = Mock()
        session.get.side_effect = [geocode, weather]
        result = answer_question("Ankara'da hava nasıl?", city="Ankara", session=session)
        self.assertIn("Ankara", result)
        self.assertIn("12 derece",result)
        self.assertIn("10 derece",result)
        self.assertEqual(session.get.call_count,2)
        self.assertNotIn("token",str(session.get.call_args_list))

    def test_weather_network_failure_does_not_invent(self):
        session = Mock()
        session.get.side_effect = Timeout("fail")
        result=answer_question("hava nasıl",city="Ankara",session=session)
        self.assertIn("erişemedim",result)
        self.assertNotIn("derece",result)

    def test_empty_geocoder_response(self):
        session = Mock()
        geo=Mock();geo.json.return_value={"results":[]}
        session.get.return_value=geo
        self.assertIn("bulunamadı",get_weather("Nonexistent",session))

    def test_time_command(self):
        self.assertEqual(answer_question("Saat kaç?",clock=datetime(2026,10,26,19,12)),"Saat 19:12.")

    def test_greeting(self):
        self.assertIn("Merhaba",answer_question("selam"))

    def test_camera_event_not_claimed(self):
        self.assertIn("henüz",answer_question("Odama kim girdi?"))

    def test_weather_codes(self):
        self.assertEqual(conditions(71),"karlı")
        self.assertEqual(conditions(95),"gök gürültülü")

    def test_no_input(self):
        self.assertIn("duyamadım",answer_question("   "))

if __name__ == '__main__': unittest.main()
