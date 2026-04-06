from django.test import TestCase

from .models import Lead


class AssistantFlowTests(TestCase):
	def _complete_strict_flow(self):
		self.client.post('/assistant/reset/')
		steps = [
			'yes',
			'Unisha, unishaa@gmail.com, 9865338866',
			'cms',
			'increase_sales',
			'seo_pro',
			'we_create',
			'mid',
			'fast',
			'confirm',
			'continue_ai',
		]
		last = None
		for msg in steps:
			last = self.client.post('/assistant/api/', {'message': msg})
		return last

	def test_required_flow_finishes_after_strict_sequence(self):
		response = self._complete_strict_flow()
		payload = response.json()

		self.assertTrue(payload['done'])
		self.assertEqual(Lead.objects.count(), 1)

		lead = Lead.objects.get()
		self.assertEqual(lead.name, 'Unisha')
		self.assertEqual(lead.phone, '9865338866')
		self.assertEqual(lead.email, 'unishaa@gmail.com')
		self.assertEqual(lead.project_type, 'cms')
		self.assertEqual(lead.expected_benefit, 'increase_sales')
		self.assertEqual(lead.content_delivery, 'we_create')
		self.assertEqual(lead.budget_range, 'mid')
		self.assertEqual(lead.timeline, 'fast')
		self.assertIsNone(lead.csat_helpful)

	def test_completed_conversation_does_not_create_duplicate_leads(self):
		self._complete_strict_flow()

		follow_up = self.client.post('/assistant/api/', {
			'message': 'just checking again',
		})

		self.assertEqual(follow_up.status_code, 200)
		self.assertEqual(Lead.objects.count(), 1)

	def test_post_save_choice_can_handoff_to_human(self):
		self.client.post('/assistant/reset/')
		for msg in [
			'yes',
			'Unisha, unishaa@gmail.com, 9865338866',
			'cms',
			'increase_sales',
			'seo_pro',
			'we_create',
			'mid',
			'fast',
			'confirm',
			'human',
		]:
			response = self.client.post('/assistant/api/', {'message': msg})

		lead = Lead.objects.get()
		self.assertEqual(lead.contact_preference, 'human')
		payload = response.json()
		self.assertTrue(payload['done'])
		self.assertEqual(payload.get('redirect_url'), '/human/')

	def test_step_lock_blocks_skipping_to_recommendation(self):
		self.client.post('/assistant/reset/')
		self.client.post('/assistant/api/', {
			'message': 'yes',
		})

		response = self.client.post('/assistant/api/', {
			'message': 'cms',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertFalse(payload['done'])
		self.assertIn('contact', payload['message'].lower())
		self.assertIn('name', payload['next_prompt'].lower())
		self.assertEqual(Lead.objects.count(), 0)

	def test_plain_greeting_gets_natural_opening(self):
		self.client.post('/assistant/reset/')

		response = self.client.post('/assistant/api/', {
			'message': 'hey',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('proceed', payload['next_prompt'].lower())
		self.assertFalse(payload['done'])

	def test_stretched_greeting_is_not_saved_as_name(self):
		self.client.post('/assistant/reset/')

		response = self.client.post('/assistant/api/', {
			'message': 'hellooooo',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('proceed', payload['next_prompt'].lower())
		self.assertFalse(payload['done'])

	def test_recommendation_message_shows_before_option_pick(self):
		self.client.post('/assistant/reset/')
		for msg in ['yes', 'Unisha, unishaa@gmail.com, 9865338866', 'cms', 'increase_sales']:
			response = self.client.post('/assistant/api/', {'message': msg})

		payload = response.json()
		self.assertIn('recommend', payload['message'].lower())
		self.assertIn('add-on', payload['next_prompt'].lower())

	def test_mixed_natural_message_is_parsed_without_invalid_block(self):
		self.client.post('/assistant/reset/')
		self.client.post('/assistant/api/', {'message': 'yes'})
		response = self.client.post('/assistant/api/', {
			'message': 'my name is john and i would like a website john@email.com +5971234567',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertNotIn('valid answer', payload['message'].lower())
		self.assertIn('option sounds closer', payload['next_prompt'].lower())

	def test_spanish_greeting_replies_in_spanish(self):
		self.client.post('/assistant/reset/')

		response = self.client.post('/assistant/api/', {
			'message': 'hola',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('Hola', payload['message'])
		self.assertIn('continuar', payload['next_prompt'].lower())
		self.assertIn('processor', payload)
		self.assertEqual(payload['processor']['phase'], 'CONTACT_CAPTURE')

	def test_crm_request_with_low_budget_triggers_stage_fit_options(self):
		self.client.post('/assistant/reset/')

		response = self.client.post('/assistant/api/', {
			'message': 'i need a crm system and my budget is below $300',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('starts around', payload['message'].lower())
		labels = [label for _, label in payload.get('quick_replies', [])]
		self.assertIn('Suggest Simpler Solution', labels)
		self.assertIn('Adjust Budget', labels)
		self.assertIn('Talk to Human', labels)

	def test_crm_request_without_budget_asks_budget_range(self):
		self.client.post('/assistant/reset/')

		response = self.client.post('/assistant/api/', {
			'message': 'we need an erp',
		})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('stage-fit', payload['message'].lower())
		self.assertIn('budget range', payload['next_prompt'].lower())
