
USE reservoir_db;


-- ------------------------------------------------------------
-- 1. Yearly summary: reservoir count + storage/level stats
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_yearly_summary AS
SELECT
    Year,
    Basin,
    COUNT(DISTINCT Reservoir_name) AS reservoir_count,
    AVG(Storage)                   AS avg_storage,
    AVG(`Level`)                   AS avg_level,
    AVG(Storage_Percentage)        AS avg_storage_percentage,
    MAX(Storage)                   AS max_storage,
    MIN(Storage)                   AS min_storage
FROM fact_reservoir_level
GROUP BY Year, Basin;


-- ------------------------------------------------------------
-- 2. Monthly summary: monthly average storage/level + observation count
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_monthly_summary AS
SELECT
    Year,
    Month,
    Month_Name,
    Basin,
    AVG(Storage)            AS avg_storage,
    AVG(`Level`)             AS avg_level,
    AVG(Storage_Percentage) AS avg_storage_percentage,
    COUNT(*)                AS observations
FROM fact_reservoir_level
GROUP BY Year, Month, Month_Name, Basin;


-- ------------------------------------------------------------
-- 3. Per-reservoir date-wise trend (for Power BI line charts)
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_trend AS
SELECT
    Reservoir_name,
    Basin,
    `Date`,
    Year,
    Month,
    Month_Name,
    Storage,
    `Level`,
    Full_reservoir_level,
    Live_capacity_FRL,
    Storage_Percentage
FROM fact_reservoir_level;


-- ------------------------------------------------------------
-- 4. Latest available status per reservoir
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_latest_status AS
SELECT
    Reservoir_name,
    Basin,
    Agency_name,
    `Date` AS latest_date,
    Storage,
    `Level`,
    Storage_Percentage,
    Full_reservoir_level,
    Live_capacity_FRL
FROM (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY Reservoir_name
            ORDER BY `Date` DESC
        ) AS rn
    FROM fact_reservoir_level f
) ranked
WHERE rn = 1;


-- ------------------------------------------------------------
-- 5. Capacity utilization detail (Storage as % of live capacity)
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_capacity_utilization AS
SELECT
    Reservoir_name,
    Basin,
    `Date`,
    Year,
    Month,
    Storage,
    Live_capacity_FRL,
    Storage_Percentage AS capacity_utilization_pct
FROM fact_reservoir_level
WHERE Live_capacity_FRL IS NOT NULL
  AND Storage IS NOT NULL;


-- ------------------------------------------------------------
-- 6. Change vs previous observation (row-level, already computed
--    in the fact table by create_hive_tables.py)
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_change AS
SELECT
    Reservoir_name,
    Basin,
    `Date`,
    Year,
    Month,
    Storage,
    Previous_Storage,
    Storage_Change,
    Storage_Change_Percentage
FROM fact_reservoir_level;


-- ------------------------------------------------------------
-- 7. Basin-wise summary
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS reservoir_basin_summary AS
SELECT
    Basin,
    COUNT(DISTINCT Reservoir_name) AS reservoir_count,
    AVG(Storage)                   AS avg_storage,
    SUM(Storage)                   AS total_storage,
    AVG(Storage_Percentage)        AS avg_storage_percentage,
    MIN(`Date`)                    AS earliest_date,
    MAX(`Date`)                    AS latest_date
FROM fact_reservoir_level
GROUP BY Basin;


-- ------------------------------------------------------------

-- ------------------------------------------------------------
SELECT
    COUNT(*)                                            AS total_rows,
    COUNT(DISTINCT Reservoir_name, `Date`)               AS distinct_reservoir_dates,
    SUM(CASE WHEN Reservoir_name IS NULL THEN 1 ELSE 0 END)   AS missing_reservoir,
    SUM(CASE WHEN `Date` IS NULL THEN 1 ELSE 0 END)            AS missing_date,
    SUM(CASE WHEN Storage IS NULL THEN 1 ELSE 0 END)           AS missing_storage,
    SUM(CASE WHEN `Level` IS NULL THEN 1 ELSE 0 END)           AS missing_level,
    SUM(CASE WHEN Live_capacity_FRL IS NULL THEN 1 ELSE 0 END) AS missing_capacity
FROM fact_reservoir_level;
