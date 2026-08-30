import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class CuratedSitesResult(BaseModel):
    """
    Schema for LLM site curation: returns the integer indexes of the selected candidate URLs.
    """
    selected_indexes: List[int] = Field(
        default_factory=list,
        description="List of 1-based integer indexes corresponding to the selected candidate URLs."
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Brief reasoning for the selection."
    )


class PropertyListing(BaseModel):
    """
    Structured schema representing a single real estate property listing with enriched title-based details.
    """
    title: str = Field(
        ...,
        description="Headline or title of the property listing."
    )
    price: Optional[str] = Field(
        default=None,
        description="Sale or rent price (e.g., 'R$ 450.000', 'R$ 2.500/mês')."
    )
    transaction_type: Optional[str] = Field(
        default=None,
        description="Type of transaction: 'Venda' (Sale), 'Aluguel' (Rent), 'Temporada' (Seasonal)."
    )
    property_type: Optional[str] = Field(
        default=None,
        description="Category of property: 'Apartamento', 'Casa', 'Terreno', 'Comercial', 'Cobertura', etc."
    )
    city: Optional[str] = Field(
        default=None,
        description="City where the property is located."
    )
    neighborhood: Optional[str] = Field(
        default=None,
        description="Neighborhood or district (e.g., 'Cambuí', 'Taquaral', 'Centro')."
    )
    address: Optional[str] = Field(
        default=None,
        description="Street name and number if available."
    )
    bedrooms: Optional[int] = Field(
        default=None,
        description="Number of bedrooms / dormitórios."
    )
    suites: Optional[int] = Field(
        default=None,
        description="Number of suites / suítes mentioned in title or description."
    )
    bathrooms: Optional[int] = Field(
        default=None,
        description="Number of bathrooms / banheiros."
    )
    parking_spots: Optional[int] = Field(
        default=None,
        description="Number of parking spots / vagas de garagem."
    )
    area_m2: Optional[float] = Field(
        default=None,
        description="Total or usable area in square meters (m²)."
    )
    amenities: List[str] = Field(
        default_factory=list,
        description="List of specific amenities found in title or description (e.g., 'Piscina', 'Churrasqueira', 'Condomínio Fechado', 'Armários Planejados', 'Varanda Gourmet', 'Vista Livre', 'Aceita Pet')."
    )
    financing_accepted: Optional[bool] = Field(
        default=None,
        description="Whether property explicitly accepts financing ('Aceita Financiamento' / 'FGTS')."
    )
    highlights: Optional[str] = Field(
        default=None,
        description="Short key highlight or differentiator extracted from the title/headline (e.g. 'Nascente com vista panorâmica', 'Reformada em condomínio fechado')."
    )
    condo_fee: Optional[str] = Field(
        default=None,
        description="Monthly condominium fee (Condomínio), if mentioned."
    )
    iptu: Optional[str] = Field(
        default=None,
        description="IPTU annual or monthly tax, if mentioned."
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief summary of key features and amenities."
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL of the website where this listing was found."
    )

    @field_validator("title", "price", "neighborhood", "city", "property_type", mode="before")
    @classmethod
    def clean_text_field(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            cleaned = v.strip()
            return cleaned if cleaned else None
        return v

    def get_numeric_price(self) -> float:
        """Helper to extract a clean float price value from the formatted string."""
        if not self.price:
            return 0.0
        cleaned = re.sub(r"[^\d,.]", "", self.price)
        if not cleaned:
            return 0.0

        if "," in cleaned and "." in cleaned:
            # e.g., 1.250.000,50
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            # e.g., 4500,50
            cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            if cleaned.count(".") > 1:
                # e.g., 1.250.000
                cleaned = cleaned.replace(".", "")
            else:
                parts = cleaned.split(".")
                if len(parts[1]) == 3:
                    # e.g., 450.000 (thousands separator in BRL/EUR)
                    cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def get_price_per_m2(self) -> Optional[float]:
        """Calculates the price per square meter if area and price are valid."""
        num_price = self.get_numeric_price()
        if num_price > 0 and self.area_m2 and self.area_m2 > 0:
            return round(num_price / self.area_m2, 2)
        return None


class PropertyExtractionResult(BaseModel):
    """
    Container schema for multiple extracted property listings from a webpage.
    """
    properties: List[PropertyListing] = Field(
        default_factory=list,
        description="List of all valid property listings identified on the page."
    )
