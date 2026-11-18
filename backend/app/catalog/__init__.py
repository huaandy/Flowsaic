"""Scrapers for SAU's public catalog (catalog.saumag.edu). No login.

The catalog's list pages (content.php) sit behind an AWS WAF bot challenge. We never try
to get past it: a list page we need is saved once by a person from their own browser
(see degree_maps.py), and only the detail pages, which answer plain HTTP, are fetched.
"""
