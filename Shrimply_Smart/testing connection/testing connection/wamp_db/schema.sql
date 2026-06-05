-- Feeder bridge table for WeMos (distance + servo state)
-- Uses the same MySQL database as Fishpond_Water_Monitoring/config.php

CREATE DATABASE IF NOT EXISTS `shrimply_smart`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

USE `shrimply_smart`;

CREATE TABLE IF NOT EXISTS `api_feederreading` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `timestamp` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `distance_cm` DOUBLE NULL,
  `servo_state` ENUM('ON','OFF') NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
