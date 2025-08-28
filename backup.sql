-- MySQL dump 10.13  Distrib 8.0.42, for Win64 (x86_64)
--
-- Host: localhost    Database: tts_db
-- ------------------------------------------------------
-- Server version	8.0.42

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `aerich`
--

DROP TABLE IF EXISTS `aerich`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `aerich` (
  `id` int NOT NULL AUTO_INCREMENT,
  `version` varchar(255) NOT NULL,
  `app` varchar(100) NOT NULL,
  `content` json NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `aerich`
--

LOCK TABLES `aerich` WRITE;
/*!40000 ALTER TABLE `aerich` DISABLE KEYS */;
INSERT INTO `aerich` VALUES (1,'0_20250522160300_init.py','models','{\"models.App\": {\"app\": \"models\", \"name\": \"models.App\", \"table\": \"app\", \"indexes\": [], \"managed\": null, \"abstract\": false, \"pk_field\": {\"name\": \"id\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"id\", \"docstring\": null, \"generated\": true, \"field_type\": \"IntField\", \"constraints\": {\"ge\": -2147483648, \"le\": 2147483647}, \"description\": null, \"python_type\": \"int\", \"db_field_types\": {\"\": \"INT\"}}, \"docstring\": \"独立的应用实体\\n- name: 应用名称（唯一）\\n- description: 应用描述\", \"fk_fields\": [], \"m2m_fields\": [{\"name\": \"devices\", \"unique\": true, \"default\": null, \"indexed\": true, \"through\": \"device_app\", \"nullable\": false, \"docstring\": null, \"generated\": false, \"on_delete\": \"CASCADE\", \"_generated\": true, \"field_type\": \"ManyToManyFieldInstance\", \"model_name\": \"models.Device\", \"constraints\": {}, \"description\": null, \"forward_key\": \"device_id\", \"python_type\": \"models.Device\", \"backward_key\": \"app_id\", \"related_name\": \"apps\", \"db_constraint\": true}], \"o2o_fields\": [], \"data_fields\": [{\"name\": \"name\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"name\", \"docstring\": null, \"generated\": false, \"field_type\": \"CharField\", \"constraints\": {\"max_length\": 255}, \"description\": null, \"python_type\": \"str\", \"db_field_types\": {\"\": \"VARCHAR(255)\", \"oracle\": \"NVARCHAR2(255)\"}}, {\"name\": \"description\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"db_column\": \"description\", \"docstring\": null, \"generated\": false, \"field_type\": \"CharField\", \"constraints\": {\"max_length\": 255}, \"description\": null, \"python_type\": \"str\", \"db_field_types\": {\"\": \"VARCHAR(255)\", \"oracle\": \"NVARCHAR2(255)\"}}, {\"name\": \"created_at\", \"unique\": false, \"default\": null, \"indexed\": false, \"auto_now\": false, \"nullable\": false, \"db_column\": \"created_at\", \"docstring\": null, \"generated\": false, \"field_type\": \"DatetimeField\", \"constraints\": {\"readOnly\": true}, \"description\": null, \"python_type\": \"datetime.datetime\", \"auto_now_add\": true, \"db_field_types\": {\"\": \"TIMESTAMP\", \"mssql\": \"DATETIME2\", \"mysql\": \"DATETIME(6)\", \"oracle\": \"TIMESTAMP WITH TIME ZONE\", \"postgres\": \"TIMESTAMPTZ\"}}, {\"name\": \"updated_at\", \"unique\": false, \"default\": null, \"indexed\": false, \"auto_now\": true, \"nullable\": false, \"db_column\": \"updated_at\", \"docstring\": null, \"generated\": false, \"field_type\": \"DatetimeField\", \"constraints\": {\"readOnly\": true}, \"description\": null, \"python_type\": \"datetime.datetime\", \"auto_now_add\": true, \"db_field_types\": {\"\": \"TIMESTAMP\", \"mssql\": \"DATETIME2\", \"mysql\": \"DATETIME(6)\", \"oracle\": \"TIMESTAMP WITH TIME ZONE\", \"postgres\": \"TIMESTAMPTZ\"}}, {\"name\": \"api_key\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"api_key\", \"docstring\": null, \"generated\": false, \"field_type\": \"CharField\", \"constraints\": {\"max_length\": 255}, \"description\": null, \"python_type\": \"str\", \"db_field_types\": {\"\": \"VARCHAR(255)\", \"oracle\": \"NVARCHAR2(255)\"}}], \"description\": \"应用主表\", \"unique_together\": [], \"backward_fk_fields\": [{\"name\": \"app_devices\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"docstring\": null, \"generated\": false, \"field_type\": \"BackwardFKRelation\", \"constraints\": {}, \"description\": null, \"python_type\": \"models.DeviceApp\", \"db_constraint\": true}], \"backward_o2o_fields\": []}, \"models.Device\": {\"app\": \"models\", \"name\": \"models.Device\", \"table\": \"device\", \"indexes\": [], \"managed\": null, \"abstract\": false, \"pk_field\": {\"name\": \"id\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"id\", \"docstring\": null, \"generated\": true, \"field_type\": \"IntField\", \"constraints\": {\"ge\": -2147483648, \"le\": 2147483647}, \"description\": null, \"python_type\": \"int\", \"db_field_types\": {\"\": \"INT\"}}, \"docstring\": \"设备实体\\n- name: 设备名称（唯一）\\n- apps: 多对多关联到应用（通过DeviceApp中间表）\", \"fk_fields\": [], \"m2m_fields\": [{\"name\": \"apps\", \"unique\": true, \"default\": null, \"indexed\": true, \"through\": \"device_app\", \"nullable\": false, \"docstring\": null, \"generated\": false, \"on_delete\": \"CASCADE\", \"_generated\": false, \"field_type\": \"ManyToManyFieldInstance\", \"model_name\": \"models.App\", \"constraints\": {}, \"description\": null, \"forward_key\": \"app_id\", \"python_type\": \"models.App\", \"backward_key\": \"device_id\", \"related_name\": \"devices\", \"db_constraint\": true}], \"o2o_fields\": [], \"data_fields\": [{\"name\": \"name\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"name\", \"docstring\": null, \"generated\": false, \"field_type\": \"CharField\", \"constraints\": {\"max_length\": 255}, \"description\": null, \"python_type\": \"str\", \"db_field_types\": {\"\": \"VARCHAR(255)\", \"oracle\": \"NVARCHAR2(255)\"}}, {\"name\": \"description\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"db_column\": \"description\", \"docstring\": null, \"generated\": false, \"field_type\": \"CharField\", \"constraints\": {\"max_length\": 255}, \"description\": null, \"python_type\": \"str\", \"db_field_types\": {\"\": \"VARCHAR(255)\", \"oracle\": \"NVARCHAR2(255)\"}}, {\"name\": \"created_at\", \"unique\": false, \"default\": null, \"indexed\": false, \"auto_now\": false, \"nullable\": false, \"db_column\": \"created_at\", \"docstring\": null, \"generated\": false, \"field_type\": \"DatetimeField\", \"constraints\": {\"readOnly\": true}, \"description\": null, \"python_type\": \"datetime.datetime\", \"auto_now_add\": true, \"db_field_types\": {\"\": \"TIMESTAMP\", \"mssql\": \"DATETIME2\", \"mysql\": \"DATETIME(6)\", \"oracle\": \"TIMESTAMP WITH TIME ZONE\", \"postgres\": \"TIMESTAMPTZ\"}}, {\"name\": \"updated_at\", \"unique\": false, \"default\": null, \"indexed\": false, \"auto_now\": true, \"nullable\": false, \"db_column\": \"updated_at\", \"docstring\": null, \"generated\": false, \"field_type\": \"DatetimeField\", \"constraints\": {\"readOnly\": true}, \"description\": null, \"python_type\": \"datetime.datetime\", \"auto_now_add\": true, \"db_field_types\": {\"\": \"TIMESTAMP\", \"mssql\": \"DATETIME2\", \"mysql\": \"DATETIME(6)\", \"oracle\": \"TIMESTAMP WITH TIME ZONE\", \"postgres\": \"TIMESTAMPTZ\"}}, {\"name\": \"is_active\", \"unique\": false, \"default\": true, \"indexed\": false, \"nullable\": false, \"db_column\": \"is_active\", \"docstring\": null, \"generated\": false, \"field_type\": \"BooleanField\", \"constraints\": {}, \"description\": null, \"python_type\": \"bool\", \"db_field_types\": {\"\": \"BOOL\", \"mssql\": \"BIT\", \"oracle\": \"NUMBER(1)\", \"sqlite\": \"INT\"}}], \"description\": \"设备表\", \"unique_together\": [], \"backward_fk_fields\": [{\"name\": \"device_apps\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"docstring\": null, \"generated\": false, \"field_type\": \"BackwardFKRelation\", \"constraints\": {}, \"description\": null, \"python_type\": \"models.DeviceApp\", \"db_constraint\": true}], \"backward_o2o_fields\": []}, \"models.DeviceApp\": {\"app\": \"models\", \"name\": \"models.DeviceApp\", \"table\": \"device_app\", \"indexes\": [], \"managed\": null, \"abstract\": false, \"pk_field\": {\"name\": \"id\", \"unique\": true, \"default\": null, \"indexed\": true, \"nullable\": false, \"db_column\": \"id\", \"docstring\": null, \"generated\": true, \"field_type\": \"IntField\", \"constraints\": {\"ge\": -2147483648, \"le\": 2147483647}, \"description\": null, \"python_type\": \"int\", \"db_field_types\": {\"\": \"INT\"}}, \"docstring\": \"设备与应用关联表（中间表）\\n- 包含关系专属字段：api_key\", \"fk_fields\": [{\"name\": \"device\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"docstring\": null, \"generated\": false, \"on_delete\": \"CASCADE\", \"raw_field\": \"device_id\", \"field_type\": \"ForeignKeyFieldInstance\", \"constraints\": {}, \"description\": null, \"python_type\": \"models.Device\", \"db_constraint\": true}, {\"name\": \"app\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"docstring\": null, \"generated\": false, \"on_delete\": \"CASCADE\", \"raw_field\": \"app_id\", \"field_type\": \"ForeignKeyFieldInstance\", \"constraints\": {}, \"description\": null, \"python_type\": \"models.App\", \"db_constraint\": true}], \"m2m_fields\": [], \"o2o_fields\": [], \"data_fields\": [{\"name\": \"app_id\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"db_column\": \"app_id\", \"docstring\": null, \"generated\": false, \"field_type\": \"IntField\", \"constraints\": {\"ge\": -2147483648, \"le\": 2147483647}, \"description\": null, \"python_type\": \"int\", \"db_field_types\": {\"\": \"INT\"}}, {\"name\": \"device_id\", \"unique\": false, \"default\": null, \"indexed\": false, \"nullable\": false, \"db_column\": \"device_id\", \"docstring\": null, \"generated\": false, \"field_type\": \"IntField\", \"constraints\": {\"ge\": -2147483648, \"le\": 2147483647}, \"description\": null, \"python_type\": \"int\", \"db_field_types\": {\"\": \"INT\"}}], \"description\": \"设备应用关联表\", \"unique_together\": [[\"device\", \"app\"]], \"backward_fk_fields\": [], \"backward_o2o_fields\": []}}');
/*!40000 ALTER TABLE `aerich` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `app`
--

DROP TABLE IF EXISTS `app`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `app` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` varchar(255) NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `api_key` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `api_key` (`api_key`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='应用主表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `app`
--

LOCK TABLES `app` WRITE;
/*!40000 ALTER TABLE `app` DISABLE KEYS */;
INSERT INTO `app` VALUES (1,'门诊导诊','251-门诊导诊','2025-05-23 09:43:04.047297','2025-05-23 09:43:04.047297','app-55x3XRlUpLaUd35yjkt7Qv2s'),(2,'医疗数字人-chatflow','医疗数字人-chatflow-251','2025-05-23 11:47:22.361137','2025-05-23 11:47:22.361137','app-pkUUdtIPcZtv1hSPQE4rE1pz'),(7,'254-医疗','254-医疗','2025-05-23 17:08:15.855704','2025-05-23 17:08:15.855704','app-M8a1xwQumic0PDm17P4qqsSy'),(8,'254-科技馆','254-科技馆','2025-05-26 11:22:51.289550','2025-05-26 11:22:51.289550','app-KSHAJY5t0rfv4qPKET72ZO5M'),(9,'253-医疗','253-医疗-chatflow','2025-05-27 09:08:39.016361','2025-05-27 09:08:39.016361','app-pNPcBbQL13p850kDHbslue9N'),(10,'251_律师','251_律师','2025-05-27 11:44:31.144647','2025-05-27 11:44:31.144647','app-w6RiQQRNVDWkfvbf1Q1PCnuw');
/*!40000 ALTER TABLE `app` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `device`
--

DROP TABLE IF EXISTS `device`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `device` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `description` varchar(255) NOT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `updated_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `device`
--

LOCK TABLES `device` WRITE;
/*!40000 ALTER TABLE `device` DISABLE KEYS */;
INSERT INTO `device` VALUES (1,'a79542e26f2067122fb387e373d387fc','小米平板','2025-05-23 09:42:09.894965','2025-05-23 09:42:09.894965',1),(2,'admin-web','开发测试网页版','2025-05-23 09:42:30.813381','2025-05-23 09:42:30.813381',1);
/*!40000 ALTER TABLE `device` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `device_app`
--

DROP TABLE IF EXISTS `device_app`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_app` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_id` int NOT NULL,
  `device_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uid_device_app_device__554ba4` (`device_id`,`app_id`),
  KEY `fk_device_a_app_0160826c` (`app_id`),
  CONSTRAINT `fk_device_a_app_0160826c` FOREIGN KEY (`app_id`) REFERENCES `app` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_device_a_device_0949943f` FOREIGN KEY (`device_id`) REFERENCES `device` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='设备应用关联表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `device_app`
--

LOCK TABLES `device_app` WRITE;
/*!40000 ALTER TABLE `device_app` DISABLE KEYS */;
INSERT INTO `device_app` VALUES (1,1,1),(4,2,1),(2,1,2),(3,2,2),(6,7,2),(7,8,2),(8,9,2),(9,10,2);
/*!40000 ALTER TABLE `device_app` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-06-03 10:35:10
