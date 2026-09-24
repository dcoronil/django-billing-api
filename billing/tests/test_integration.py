from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from billing.models import Barrel, Invoice, InvoiceLine, Provider


User = get_user_model()


class BillingApiTestCase(APITestCase):
    def create_provider(self, suffix):
        return Provider.objects.create(
            name=f"Provider {suffix}",
            address=f"Address {suffix}",
            tax_id=f"TAX-{suffix}",
        )

    def create_user(self, suffix, provider=None, is_superuser=False):
        return User.objects.create_user(
            username=f"user_{suffix}",
            password="strongpass123",
            provider=provider,
            is_superuser=is_superuser,
            is_staff=is_superuser,
        )

    def create_invoice(self, provider, suffix):
        return Invoice.objects.create(
            provider=provider,
            invoice_no=f"INV-{suffix}",
            issued_on=date(2026, 1, 1),
        )

    def create_barrel(self, provider, suffix, liters=100, billed=False):
        return Barrel.objects.create(
            provider=provider,
            number=f"BAR-{suffix}",
            oil_type="Olive",
            liters=liters,
            billed=billed,
        )


class InvoiceIntegrationTests(BillingApiTestCase):
    def test_add_line_rejects_billing_the_same_barrel_twice(self):
        provider = self.create_provider("A")
        user = self.create_user("a", provider=provider)
        barrel = self.create_barrel(provider, "A", liters=120)
        invoice = self.create_invoice(provider, "A")
        invoice.add_line_for_barrel(
            barrel=barrel,
            liters=120,
            unit_price_per_liter=Decimal("2.50"),
            description="First billing",
        )

        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse("invoice-add-line", args=[invoice.id]),
            {
                "barrel": barrel.id,
                "liters": 120,
                "unit_price": "2.50",
                "description": "Duplicate billing",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(str(response.data["detail"]), "barrel has already been billed")
        self.assertEqual(InvoiceLine.objects.count(), 1)

    def test_add_line_returns_400_when_barrel_provider_does_not_match_invoice_provider(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        user_a = self.create_user("a", provider=provider_a)
        invoice_a = self.create_invoice(provider_a, "A")
        barrel_b = self.create_barrel(provider_b, "B", liters=150)
        payload = {
            "barrel": barrel_b.id,
            "liters": barrel_b.liters,
            "unit_price": "2.50",
            "description": "Full barrel",
        }

        self.client.force_authenticate(user=user_a)
        response = self.client.post(
            reverse("invoice-add-line", args=[invoice_a.id]),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        self.assertEqual(
            str(response.data["detail"]),
            "barrel provider must match invoice provider",
        )
        self.assertEqual(InvoiceLine.objects.count(), 0)
        barrel_b.refresh_from_db()
        self.assertFalse(barrel_b.billed)

    def test_invoice_list_and_detail_are_scoped_to_logged_in_provider(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        user_a = self.create_user("a", provider=provider_a)
        invoice_a = self.create_invoice(provider_a, "A")
        invoice_b = self.create_invoice(provider_b, "B")

        self.client.force_authenticate(user=user_a)
        list_response = self.client.get(reverse("invoice-list"))
        detail_response = self.client.get(reverse("invoice-detail", args=[invoice_b.id]))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["id"], invoice_a.id)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)


class BarrelIntegrationTests(BillingApiTestCase):
    def test_create_barrel_uses_logged_in_user_provider(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        user_a = self.create_user("a", provider=provider_a)
        payload = {
            "provider": provider_b.id,
            "number": "BAR-A",
            "oil_type": "Olive",
            "liters": 120,
        }

        self.client.force_authenticate(user=user_a)
        response = self.client.post(reverse("barrel-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["provider"], provider_a.id)
        barrel = Barrel.objects.get(id=response.data["id"])
        self.assertEqual(barrel.provider_id, provider_a.id)

    def test_delete_barrel_returns_controlled_error_when_it_is_used_in_invoice_line(self):
        provider = self.create_provider("A")
        user = self.create_user("a", provider=provider)
        barrel = self.create_barrel(provider, "A", liters=120)
        invoice = self.create_invoice(provider, "A")
        invoice.add_line_for_barrel(
            barrel=barrel,
            liters=120,
            unit_price_per_liter=Decimal("2.50"),
            description="Full barrel",
        )

        self.client.force_authenticate(user=user)
        response = self.client.delete(reverse("barrel-detail", args=[barrel.id]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Cannot delete barrel because it is used in an invoice line.",
        )
        self.assertTrue(Barrel.objects.filter(id=barrel.id).exists())


class ProviderIntegrationTests(BillingApiTestCase):
    def test_superuser_provider_list_returns_all_providers(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        admin = self.create_user("admin", is_superuser=True)

        self.client.force_authenticate(user=admin)
        response = self.client.get(reverse("provider-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in response.data},
            set(Provider.objects.values_list("id", flat=True)),
        )

    def test_superuser_can_access_provider_detail(self):
        provider = self.create_provider("A")
        admin = self.create_user("admin", is_superuser=True)

        self.client.force_authenticate(user=admin)
        response = self.client.get(reverse("provider-detail", args=[provider.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], provider.id)
        self.assertEqual(response.data["name"], provider.name)

    def test_normal_user_provider_list_returns_only_own_provider_with_liters_fields(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        user_a = self.create_user("a", provider=provider_a)
        self.create_barrel(provider_a, "A1", liters=120, billed=True)
        self.create_barrel(provider_a, "A2", liters=80, billed=False)
        self.create_barrel(provider_b, "B1", liters=200, billed=True)

        self.client.force_authenticate(user=user_a)
        response = self.client.get(reverse("provider-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], provider_a.id)
        self.assertEqual(response.data[0]["billed_liters"], 120)
        self.assertEqual(response.data[0]["liters_to_bill"], 80)

    def test_normal_user_cannot_access_other_provider_detail(self):
        provider_a = self.create_provider("A")
        provider_b = self.create_provider("B")
        user_a = self.create_user("a", provider=provider_a)

        self.client.force_authenticate(user=user_a)
        response = self.client.get(reverse("provider-detail", args=[provider_b.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
