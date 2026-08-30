import pytest
from src.extractor.schemas import PropertyListing, CuratedSitesResult, PropertyExtractionResult


def test_property_listing_creation_and_cleaning():
    listing = PropertyListing(
        title="  Lindo Apartamento 3 Quartos  ",
        price="R$ 750.000,00",
        neighborhood="  Ipanema  ",
        city="Rio de Janeiro",
        bedrooms=3,
        suites=1,
        area_m2=120.0,
        amenities=["Piscina", "Varanda Gourmet"],
        financing_accepted=True
    )

    assert listing.title == "Lindo Apartamento 3 Quartos"
    assert listing.neighborhood == "Ipanema"
    assert listing.bedrooms == 3
    assert listing.suites == 1
    assert listing.financing_accepted is True


def test_property_listing_numeric_price():
    listing1 = PropertyListing(title="Casa", price="R$ 1.250.000")
    assert listing1.get_numeric_price() == 1250000.0

    listing2 = PropertyListing(title="Apartamento", price="R$ 4.500,50/mês")
    assert listing2.get_numeric_price() == 4500.50

    listing_empty = PropertyListing(title="Terreno", price=None)
    assert listing_empty.get_numeric_price() == 0.0


def test_property_listing_price_per_m2():
    listing = PropertyListing(
        title="Cobertura",
        price="R$ 2.000.000",
        area_m2=200.0
    )
    assert listing.get_price_per_m2() == 10000.0

    listing_no_area = PropertyListing(
        title="Studio",
        price="R$ 300.000",
        area_m2=None
    )
    assert listing_no_area.get_price_per_m2() is None


def test_curated_sites_schema():
    curated = CuratedSitesResult(
        selected_indexes=[1, 3],
        reasoning="Reputable listing portals with direct search results"
    )
    assert curated.selected_indexes == [1, 3]
    assert "Reputable" in curated.reasoning


def test_property_extraction_result():
    result = PropertyExtractionResult(
        properties=[
            PropertyListing(title="Imóvel 1", price="R$ 500.000"),
            PropertyListing(title="Imóvel 2", price="R$ 600.000"),
        ]
    )
    assert len(result.properties) == 2
