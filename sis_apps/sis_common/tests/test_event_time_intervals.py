from sis_common.tests.test_institutional_events import URL, EventFixture


class EventOffsetIntervalTests(EventFixture):
    def test_explicit_folds_allow_positive_event_and_calendar_intervals(self):
        bounds = {"debut": "2027-10-31T02:45:00+02:00", "fin": "2027-10-31T02:15:00+01:00"}
        response = self.client.post(URL, {**self.payload, **bounds}, format="json")
        assert response.status_code == 201, response.data
        calendar = self.client.get(URL, bounds)
        assert calendar.status_code == 200, calendar.data
        assert [row["id"] for row in calendar.data["results"]] == [response.data["id"]]

    def test_explicit_folds_reject_negative_elapsed_intervals_without_writes(self):
        bounds = {"debut": "2027-10-31T02:15:00+01:00", "fin": "2027-10-31T02:45:00+02:00"}
        before = self.counts()
        response = self.client.post(URL, {**self.payload, **bounds}, format="json")
        assert response.status_code == 400, response.data
        assert self.counts() == before
        calendar = self.client.get(URL, bounds)
        assert calendar.status_code == 400, calendar.data
