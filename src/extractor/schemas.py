from typing import List, Optional
from pydantic import BaseModel, Field


class CuratedSitesResult(BaseModel):
    """
    Schema for LLM site curation: returns the integer indexes of the selected candidate URLs.
    """
    selected_indexes: List[int] = Field(
        default_factory=list,
        description="List of 1-based integer indexes corresponding to the selected candidate URLs."
    )
    reasoning: Optional[str] = Field(
        None,
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
        None,
        description="Sale or rent price (e.g., 'R$ 450.000', 'R$ 2.500/mês')."
    )
    transaction_type: Optional[str] = Field(
        None,
        description="Type of transaction: 'Venda' (Sale), 'Aluguel' (Rent), 'Temporada' (Seasonal)."
    )
    property_type: Optional[str] = Field(
        None,
        description="Category of property: 'Apartamento', 'Casa', 'Terreno', 'Comercial', 'Cobertura', etc."
    )
    city: Optional[str] = Field(
        None,
        description="City where the property is located."
    )
    neighborhood: Optional[str] = Field(
        None,
        description="Neighborhood or district (e.g., 'Cambuí', 'Taquaral', 'Centro')."
    )
    address: Optional[str] = Field(
        None,
        description="Street name and number if available."
    )
    bedrooms: Optional[int] = Field(
        None,
        description="Number of bedrooms / dormitórios."
    )
    suites: Optional[int] = Field(
        None,
        description="Number of suites / suítes mentioned in title or description."
    )
    bathrooms: Optional[int] = Field(
        None,
        description="Number of bathrooms / banheiros."
    )
    parking_spots: Optional[int] = Field(
        None,
        description="Number of parking spots / vagas de garagem."
    )
    area_m2: Optional[float] = Field(
        None,
        description="Total or usable area in square meters (m²)."
    )
    amenities: List[str] = Field(
        default_factory=list,
        description="List of specific amenities found in title or description (e.g., 'Piscina', 'Churrasqueira', 'Condomínio Fechado', 'Armários Planejados', 'Varanda Gourmet', 'Vista Livre', 'Aceita Pet')."
    )
    financing_accepted: Optional[bool] = Field(
        None,
        description="Whether property explicitly accepts financing ('Aceita Financiamento' / 'FGTS')."
    )
    highlights: Optional[str] = Field(
        None,
        description="Short key highlight or differentiator extracted from the title/headline (e.g. 'Nascente com vista panorâmica', 'Reformada em condomínio fechado')."
    )
    condo_fee: Optional[str] = Field(
        None,
        description="Monthly condominium fee (Condomínio), if mentioned."
    )
    iptu: Optional[str] = Field(
        None,
        description="IPTU annual or monthly tax, if mentioned."
    )
    description: Optional[str] = Field(
        None,
        description="Brief summary of key features and amenities."
    )
    source_url: Optional[str] = Field(
        None,
        description="URL of the website where this listing was found."
    )


class PropertyExtractionResult(BaseModel):
    """
    Container schema for multiple extracted property listings from a webpage.
    """
    properties: List[PropertyListing] = Field(
        default_factory=list,
        description="List of all valid property listings identified on the page."
    )
