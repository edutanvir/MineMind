# MineMind - Source Inspection Report

Inspection date: 2026-11-21

## 1. NRCan Map 900A

Source:
https://ftp.maps.canada.ca/pub/nrcan_rncan/Mining-industry_Industrie-miniere/900A_and_top_100/900A.gdb.zip

Download file: 900A.gdb.zip

### Available layers
```text
             name geometry_type
0          Helium         Point
1       OilAndGas         Point
2  ProducingMines         Point
3      MetalWorks         Point
4       Top100Exp         Point
```

### Selected layer
`ProducingMines` (Primary core layer for MineMind; `MetalWorks` and `Top100Exp` retained as supplementary layers).

*(Note: Layer 0 `Helium` was inspected provisionally during initial pipeline discovery; outputs for both `ProducingMines` and `Helium` are recorded below).*

#### Core Selected Layer: `ProducingMines`

### Shape
```text
(183, 24)
```

### CRS
```text
EPSG:3978
```

### Geometry types
```text
Point    183
Name: count, dtype: int64
```

### Column names
```text
['count', 'operation_group_en', 'operation_group_fr', 'operation_nb', 'province_abr', 'province_en', 'province_fr', 'province_nb', 'operation_name_en', 'operation_name_fr', 'operator_owners_en', 'operator_owners_fr', 'facilities_code_en_spelt', 'facilities_code_fr_spelt', 'city_en', 'city_fr', 'product_group_en_spelt', 'product_group_fr_spelt', 'product_en_spelt', 'product_fr_spelt', 'latitude', 'longitude', 'website', 'geometry']
```

### First three records
```text
   count operation_group_en operation_group_fr  operation_nb province_abr                province_en              province_fr  province_nb operation_name_en operation_name_fr     operator_owners_en     operator_owners_fr             facilities_code_en_spelt                 facilities_code_fr_spelt       city_en       city_fr product_group_en_spelt product_group_fr_spelt        product_en_spelt        product_fr_spelt   latitude  longitude                       website                         geometry
0      1        Metal mines    Mines de métaux             1          NFL  Newfoundland and Labrador  Terre-Neuve-et-Labrador            1         Valentine         Valentine     Equinox Gold Corp.     Equinox Gold Corp.               Open-pit, concentrator               Ciel ouvert, concentrateur    Millertown    Millertown        Precious metals        Métaux précieux                    Gold                      Or  48.393120 -57.101310  https://www.equinoxgold.com/   POINT (2649837.935 746079.059)
1      2        Metal mines    Mines de métaux             1          NFL  Newfoundland and Labrador  Terre-Neuve-et-Labrador            1      Voisey’s Bay      Voisey’s Bay    Vale Canada Limited    Vale Canada Limited  Open-pit, underground, concentrator  Ciel ouvert, souterraine, concentrateur  Voisey’s Bay  Voisey’s Bay            Base metals         Métaux communs  Nickel, copper, cobalt  Nickel, cuivre, cobalt  56.331659 -62.090855  https://www.vale.com/canada/  POINT (1903343.697 1309698.743)
2      3        Metal mines    Mines de métaux             1          NFL  Newfoundland and Labrador  Terre-Neuve-et-Labrador            1            Scully            Scully  Tacora Resources Inc.  Tacora Resources Inc.               Open-pit, concentrator               Ciel ouvert, concentrateur        Wabush        Wabush               Iron ore         Minerai de fer                    Iron                     Fer  52.907129 -66.912573  https://tacoraresources.com/     POINT (1804595.3 836675.421)
```

<details>
<summary>Provisional Layer Inspection (Helium - layers.iloc[0])</summary>

- **Shape**: `(10, 17)`
- **CRS**: `EPSG:3978`
- **Geometry types**: `Point: 10`
- **Column names**: `['Count', 'Province_number', 'Province_abr', 'Province_E_long', 'Province_F_Long', 'Operation_E', 'Operation_F', 'Operator_Owners_E', 'Operator_Owners_F', 'City_e', 'City_f', 'Product_e_long', 'Product_f_long', 'Latitude', 'Longitude', 'Company_website', 'geometry']`
- **First three records**:
```text
   Count  Province_number Province_abr Province_E_long Province_F_Long Operation_E Operation_F           Operator_Owners_E           Operator_Owners_F         City_e         City_f Product_e_long Product_f_long  Latitude  Longitude        Company_website                        geometry
0      1                8           SK    Saskatchewan    Saskatchewan     Mankota     Mankota  North American Helium Inc.  North American Helium Inc.  Swift Current  Swift Current         Helium         Hélium  49.37296 -107.01266  https://nahelium.com/  POINT (-865990.384 123467.827)
1      2                8           SK    Saskatchewan    Saskatchewan   Soda Lake   Soda Lake  North American Helium Inc.  North American Helium Inc.  Swift Current  Swift Current         Helium         Hélium  49.26330 -107.10730  https://nahelium.com/  POINT (-875035.354 112800.313)
2      3                8           SK    Saskatchewan    Saskatchewan    Cadillac    Cadillac  North American Helium Inc.  North American Helium Inc.  Swift Current  Swift Current         Helium         Hélium  49.77020 -107.40800  https://nahelium.com/   POINT (-885588.284 172186.95)
```
</details>


## 2. Statistics Canada

Dataset: Table 16-10-0019-01

Source:
https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1610001901

Download date: 2026-11-21

Table release/update date: 2026-11-20

### Downloaded files
- `16100019.csv` (symlinked as `1610001901.csv`, extracted from `16100019-eng.zip`)
- `1610001901_MetaData.csv`

### Dataset shape
```text
(172346, 16)
```

### Column names
```text
['REF_DATE', 'GEO', 'DGUID', 'Products', 'Variables', 'UOM', 'UOM_ID', 'SCALAR_FACTOR', 'SCALAR_ID', 'VECTOR', 'COORDINATE', 'VALUE', 'STATUS', 'SYMBOL', 'TERMINATED', 'DECIMALS']
```

### First five records
```text
  REF_DATE     GEO           DGUID                                Products          Variables            UOM UOM_ID SCALAR_FACTOR SCALAR_ID       VECTOR COORDINATE   VALUE STATUS SYMBOL TERMINATED DECIMALS
0  2020-01  Canada  2021A000011124                Aluminum (metric tonnes)  Quantity produced  Metric tonnes    214         units         0  v1146004294      1.1.1  254371                                 0
1  2020-01  Canada  2021A000011124  Aluminum, molten metal (metric tonnes)  Quantity produced  Metric tonnes    214         units         0  v1146004554      1.2.1  250396                                 0
2  2020-01  Canada  2021A000011124        Aluminum, alloys (metric tonnes)  Quantity produced  Metric tonnes    214         units         0  v1146004814      1.3.1    3975                                 0
3  2020-01  Canada  2021A000011124          Cobalt recoverable (kilograms)  Quantity produced      Kilograms    192         units         0  v1146005045      1.4.1  254663                                 0
4  2020-01  Canada  2021A000011124          Cobalt recoverable (kilograms)   Quantity shipped      Kilograms    192         units         0  v1146005061      1.4.2  278622                                 0
```

### Data types
```text
REF_DATE         str
GEO              str
DGUID            str
Products         str
Variables        str
UOM              str
UOM_ID           str
SCALAR_FACTOR    str
SCALAR_ID        str
VECTOR           str
COORDINATE       str
VALUE            str
STATUS           str
SYMBOL           str
TERMINATED       str
DECIMALS         str
dtype: object
```


## 3. Inspection Notes

- Original source files preserved unchanged.
- Actual source field names documented.
- No Silver transformations performed yet.
- No assumptions made about mine or commodity attributes.
- Statistics Canada status and symbol fields retained.
