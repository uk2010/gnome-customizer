import unittest
from pathlib import Path

from gnome_customizer.backend.settings import (
    POWER_PROFILE_CHOICES,
    POWER_PROFILE_KEY,
    POWER_PROFILES_SCHEMA,
    SettingsBackend,
    SettingsError,
)


ROOT = Path(__file__).resolve().parents[2]


class Result:
    def __init__(self, value): self.value=value
    def unpack(self): return (self.value,)


class FakePowerProfilesProxy:
    def __init__(self, profiles):
        self.active="balanced";self.profiles=profiles

    def call_sync(self, method, parameters, *_):
        if method.endswith(".Get"):
            prop=parameters.unpack()[1]
            values={"ActiveProfile":self.active,"Profiles":self.profiles,"PerformanceDegraded":""}
            return Result(values[prop])
        if method.endswith(".Set"):
            self.active=parameters.unpack()[2]
            return Result(None)
        raise AssertionError(method)


class PowerProfileTests(unittest.TestCase):
    def backend(self, profiles):
        backend=SettingsBackend();backend._power_profiles_proxy=FakePowerProfilesProxy(profiles);backend._power_profiles_proxy_loaded=True
        return backend

    def test_all_three_modes_are_always_present_in_the_selector(self):
        backend=self.backend([{"Profile":"balanced"},{"Profile":"power-saver"}])
        self.assertEqual(tuple(backend.choices(POWER_PROFILES_SCHEMA,POWER_PROFILE_KEY)),POWER_PROFILE_CHOICES)
        self.assertIn("Performance remains listed",backend.power_profile_summary())

    def test_supported_performance_profile_is_activated_through_dbus(self):
        backend=self.backend([{"Profile":"balanced"},{"Profile":"power-saver"},{"Profile":"performance","CpuDriver":"intel_pstate"}])
        backend.set(POWER_PROFILES_SCHEMA,POWER_PROFILE_KEY,"performance")
        self.assertEqual(backend.get(POWER_PROFILES_SCHEMA,POWER_PROFILE_KEY),"performance")
        self.assertIn("intel_pstate",backend.power_profile_summary())

    def test_unsupported_performance_is_not_falsely_reported_as_active(self):
        backend=self.backend([{"Profile":"balanced"},{"Profile":"power-saver"}])
        with self.assertRaisesRegex(SettingsError,"cannot be forced safely"):
            backend.set(POWER_PROFILES_SCHEMA,POWER_PROFILE_KEY,"performance")
        self.assertEqual(backend.get(POWER_PROFILES_SCHEMA,POWER_PROFILE_KEY),"balanced")

    def test_power_page_and_package_expose_the_native_service(self):
        preferences=(ROOT/"src/gnome_customizer/pages/preferences.py").read_text()
        control=(ROOT/"debian/control").read_text()
        self.assertIn('"performance":"Performance"',preferences)
        self.assertIn("power_profile_summary()",preferences)
        self.assertIn("power-profiles-daemon",control)


if __name__ == "__main__": unittest.main()
