-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `fishpond_monitoring`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE `fishpond_monitoring`;

-- Create readings table for fishpond sensor data
CREATE TABLE IF NOT EXISTS `readings` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `ts` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `temp` DOUBLE NOT NULL DEFAULT 0,
  `ph` DOUBLE NOT NULL DEFAULT 0,
  `oxygen` DOUBLE NOT NULL DEFAULT 0,
  `tds` DOUBLE NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  INDEX `idx_ts` (`ts`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
