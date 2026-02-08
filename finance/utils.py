def tenant_to_company(tenant) -> dict:
    if not tenant:
        return {
            "name": "—",
            "trade_name": "",
            "legal_form": "",
            "registration_number": "",
            "tax_id": "",
            "tax_center": "",
            "address": "",
            "contact_email": "",
            "billing_email": "",
            "phone": "",
            "website": "",
            "logo_url": "",
            "stamp_url": "",
            "signature_url": "",
            "footer_note": "",
            "bank": {},
            "mobile_money": {},
            "currency": "XOF",
        }

    # Adresse lisible
    address = tenant.display_address or ""

    # Emails
    email = tenant.billing_email or tenant.contact_email or ""

    return {
        "name": tenant.display_legal_name or tenant.name,
        "trade_name": tenant.trade_name or "",
        "legal_form": tenant.legal_form or "",
        "registration_number": tenant.registration_number or "",
        "tax_id": tenant.tax_id or "",
        "tax_center": tenant.tax_center or "",
        "address": address,
        "contact_email": tenant.contact_email or "",
        "billing_email": tenant.billing_email or "",
        "email": email,
        "phone": tenant.contact_phone or "",
        "website": tenant.website or "",
        "logo_url": tenant.logo_url or "",
        "stamp_url": tenant.stamp_url or "",
        "signature_url": tenant.signature_url or "",
        "footer_note": tenant.invoice_footer_note or "",
        "bank": tenant.bank_details or {},
        "mobile_money": tenant.mobile_money_details or {},
        "currency": tenant.currency or "XOF",
    }