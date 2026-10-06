# Selected Mosambi (Sweet Lime) Markets Configuration

This document defines the official **21 Mandi Markets** selected for the Mosambi Price Prediction & Market Intelligence system.

---

## Market Registry by Region

### 1. Andhra Pradesh (Primary Origin & Regional Hubs)
| Mandi Name | District | State | Market Role |
| :--- | :--- | :--- | :--- |
| **Anantapur APMC** | Anantapur | Andhra Pradesh | Primary Farm-Gate / Origin Hub |
| **Pulivendala APMC** | YSR Kadapa | Andhra Pradesh | Primary Farm-Gate / Origin Hub |
| **Tirupati APMC** | Tirupati | Andhra Pradesh | Regional Consumption & Trade |
| **Chittoor APMC** | Chittoor | Andhra Pradesh | Regional Processing & Wholesale |
| **Vijayawada APMC** | NTR / Krishna | Andhra Pradesh | Coastal AP Major Terminal Hub |
| **Guntur APMC** | Guntur | Andhra Pradesh | Major Commercial Trade Hub |

### 2. Telangana (Primary Origin & Wholesale Hubs)
| Mandi Name | District | State | Market Role |
| :--- | :--- | :--- | :--- |
| **Nalgonda APMC** | Nalgonda | Telangana | Key Origin & Harvest Hub |
| **Batasingaram / Gaddiannaram** | Rangareddy / Hyderabad | Telangana | Capital Metropolis Terminal Market |
| **Warangal APMC** | Warangal | Telangana | North Telangana Wholesale Hub |
| **Khammam APMC** | Khammam | Telangana | Eastern TS Regional Trade |
| **Mahabubnagar APMC** | Mahabubnagar | Telangana | Southern TS Regional Hub |

### 3. Maharashtra (Western Origin & Major Trade Hubs)
| Mandi Name | District | State | Market Role |
| :--- | :--- | :--- | :--- |
| **Rahuri APMC** | Ahilyanagar (Ahmednagar) | Maharashtra | Major Western Citrus Hub |
| **Jalna APMC** | Jalna | Maharashtra | Marathwada Regional Hub |
| **Nagpur APMC** | Nagpur | Maharashtra | National Citrus Trading Hub |
| **Pune APMC (Gultekadi)** | Pune | Maharashtra | Major Western Terminal Hub |
| **Vashi APMC** | Navi Mumbai | Maharashtra | Coastal Commercial Terminal Hub |

### 4. Major Interstate Terminal Markets (National Demand Hubs)
| Mandi Name | City / State | Primary Purpose in Model |
| :--- | :--- | :--- |
| **Azadpur APMC** | Delhi NCR | **National Benchmark Price Index** (Asia's Largest Fruit Market) |
| **Bengaluru (Kalasipalyam / Singena Agrahara)** | Karnataka | Major South-Indian Metropolis Terminal Market |
| **Chennai (Koyambedu APMC)** | Tamil Nadu | Major South-East Coastal Consumption Market |
| **Surat APMC** | Gujarat | Industrial West Consumption Hub |
| **Ahmedabad APMC** | Gujarat | Commercial Gujarat Terminal Market |

---

## Network Topology Matrix

```mermaid
graph TD
    subgraph Origin Hubs (Farmers & Pickers)
        AP[AP Mandis: Anantapur, Pulivendala, Chittoor]
        TS[TS Mandis: Nalgonda, Warangal, Khammam]
        MH[MH Mandis: Rahuri, Jalna, Nagpur]
    end

    subgraph Transit & Regional Wholesale
        HYD[Hyderabad - Batasingaram]
        VJA[Vijayawada & Guntur]
        PNE[Pune & Vashi]
    end

    subgraph National Terminal Markets
        DEL[Azadpur Delhi APMC - Benchmark]
        BLR[Bengaluru APMC]
        MAA[Chennai APMC]
        GUJ[Surat & Ahmedabad APMC]
    end

    AP --> HYD
    AP --> BLR
    AP --> MAA
    TS --> HYD
    TS --> DEL
    MH --> PNE
    MH --> GUJ
    MH --> DEL
```
