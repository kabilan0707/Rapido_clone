-- ============================================================
--  RAPIDO CLONE — COMPLETE DATABASE SETUP
--  Run this in MySQL Workbench or terminal:
--  mysql -u root -p < database_setup.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS rapido_clone;
USE rapido_clone;

-- ============================================================
-- TABLE 1: USERS (Customers who book rides)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    mobile      VARCHAR(15)  NOT NULL UNIQUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 2: RIDERS (Captains / Drivers)
-- ============================================================
CREATE TABLE IF NOT EXISTS riders (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    mobile        VARCHAR(15)  NOT NULL UNIQUE,
    vehicle_no    VARCHAR(20)  NOT NULL,
    is_online     TINYINT(1)   DEFAULT 0,
    rating        DECIMAL(3,2) DEFAULT 5.00,
    total_rides   INT          DEFAULT 0,
    total_earnings DECIMAL(10,2) DEFAULT 0.00,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE 3: RIDES (Core ride data)
-- ============================================================
CREATE TABLE IF NOT EXISTS rides (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    user_id       INT          NOT NULL,
    rider_id      INT          DEFAULT NULL,

    -- Location details
    pickup        VARCHAR(255) NOT NULL,
    drop_location VARCHAR(255) NOT NULL,
    pickup_lat    DECIMAL(10,7) NOT NULL,
    pickup_lng    DECIMAL(10,7) NOT NULL,
    drop_lat      DECIMAL(10,7) NOT NULL,
    drop_lng      DECIMAL(10,7) NOT NULL,

    -- Fare details
    distance      DECIMAL(8,2) NOT NULL,
    amount        DECIMAL(8,2) NOT NULL,

    -- Ride tracking
    otp           VARCHAR(4)   DEFAULT NULL,
    status        ENUM('REQUESTED','ACCEPTED','STARTED','COMPLETED','CANCELLED')
                  DEFAULT 'REQUESTED',
    payment_method ENUM('cash','upi') DEFAULT 'cash',
    rating        INT          DEFAULT NULL,   -- 1 to 5 stars from user

    -- Timestamps
    requested_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    accepted_at   TIMESTAMP    NULL,
    started_at    TIMESTAMP    NULL,
    completed_at  TIMESTAMP    NULL,

    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- ============================================================
-- TABLE 4: RATINGS (User rates Captain after ride)
-- ============================================================
CREATE TABLE IF NOT EXISTS ratings (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    ride_id    INT NOT NULL,
    user_id    INT NOT NULL,
    rider_id   INT NOT NULL,
    stars      INT NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment    VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ride_id)  REFERENCES rides(id),
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- ============================================================
-- SAMPLE DATA (optional — for testing)
-- ============================================================
INSERT IGNORE INTO users (name, mobile) VALUES
  ('Arjun Kumar',   '9876543210'),
  ('Priya Devi',    '9123456780'),
  ('Karthik Raja',  '9988776655');

INSERT IGNORE INTO riders (name, mobile, vehicle_no) VALUES
  ('Murugan S',     '9111222333', 'TN 05 AB 1234'),
  ('Selvam R',      '9444555666', 'TN 09 CD 5678');

-- ============================================================
-- USEFUL VIEWS (optional — for admin/dashboard)
-- ============================================================
CREATE OR REPLACE VIEW ride_details AS
SELECT
    r.id           AS ride_id,
    u.name         AS user_name,
    u.mobile       AS user_mobile,
    rd.name        AS rider_name,
    rd.mobile      AS rider_mobile,
    rd.vehicle_no,
    r.pickup,
    r.drop_location,
    r.distance,
    r.amount,
    r.status,
    r.payment_method,
    r.rating,
    r.requested_at,
    r.completed_at
FROM rides r
JOIN users u  ON r.user_id  = u.id
LEFT JOIN riders rd ON r.rider_id = rd.id;

-- ============================================================
-- END OF SETUP
-- ============================================================
-- To verify:  SHOW TABLES;
--             SELECT * FROM ride_details;
