mysqldump: [Warning] Using a password on the command line interface can be insecure.
-- MySQL dump 10.13  Distrib 8.0.46, for Linux (x86_64)
--
-- Host: localhost    Database: silver_vitality
-- ------------------------------------------------------
-- Server version	8.0.46

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
-- Table structure for table `activities`
--

DROP TABLE IF EXISTS `activities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activities` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '活动ID',
  `captain_id` bigint NOT NULL COMMENT '队长用户ID',
  `category_id` bigint NOT NULL COMMENT '活动分类ID',
  `title` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '活动标题',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '活动描述（适老化大字号排版）',
  `cover_image` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '封面图片URL',
  `location_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '地点名称（如''中山公园北门''）',
  `location_address` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '详细地址',
  `location_lat` decimal(10,7) DEFAULT NULL COMMENT '纬度(高德坐标系)',
  `location_lng` decimal(10,7) DEFAULT NULL COMMENT '经度(高德坐标系)',
  `city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '城市(文本，展示用)',
  `district` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '区/县(文本，展示用)',
  `province_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '省份代码(GB/T 2260)',
  `city_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '城市代码(同城活动筛选用)',
  `district_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '区县代码',
  `street_id` bigint DEFAULT NULL COMMENT '合作街道ID(如使用合作场地)',
  `start_time` datetime NOT NULL COMMENT '活动开始时间',
  `end_time` datetime NOT NULL COMMENT '活动结束时间',
  `signup_deadline` datetime DEFAULT NULL COMMENT '报名截止时间',
  `max_participants` int NOT NULL COMMENT '最大参与人数',
  `min_participants` int DEFAULT '1' COMMENT '最少成团人数',
  `current_participants` int NOT NULL DEFAULT '0' COMMENT '当前报名人数',
  `has_waitlist` tinyint(1) NOT NULL DEFAULT '0' COMMENT '满员后是否启用候补',
  `price` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '费用(0=免费)',
  `safety_level` varchar(5) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'green' COMMENT '安全等级: green/yellow/red',
  `age_min` int DEFAULT NULL COMMENT '最小年龄限制',
  `age_max` int DEFAULT NULL COMMENT '最大年龄限制',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '状态: draft/pending/approved/rejected/ongoing/completed/cancelled',
  `reject_reason` text COLLATE utf8mb4_unicode_ci COMMENT '驳回原因',
  `weather_alert` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '天气预警: none/yellow/red',
  `weather_check_at` datetime DEFAULT NULL COMMENT '最后天气检测时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段(预留)',
  `version` int NOT NULL DEFAULT '1' COMMENT '乐观锁版本号',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_activities_captain_id` (`captain_id`),
  KEY `ix_activities_category_id` (`category_id`),
  KEY `ix_activities_city` (`city`),
  KEY `ix_activities_city_code` (`city_code`),
  KEY `ix_activities_street_id` (`street_id`),
  KEY `ix_activities_start_time` (`start_time`),
  KEY `ix_activities_status` (`status`),
  KEY `ix_activities_deleted_at` (`deleted_at`),
  CONSTRAINT `fk_activities_captain_id` FOREIGN KEY (`captain_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activities_category_id` FOREIGN KEY (`category_id`) REFERENCES `activity_categories` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activities_street_id` FOREIGN KEY (`street_id`) REFERENCES `partner_streets` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_albums`
--

DROP TABLE IF EXISTS `activity_albums`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_albums` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '照片ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '上传者ID',
  `image_url` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图片URL',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片说明',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '排序号',
  `created_at` datetime NOT NULL COMMENT '上传时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_albums_activity_id` (`activity_id`),
  KEY `fk_activity_albums_user_id` (`user_id`),
  CONSTRAINT `fk_activity_albums_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_albums_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动相册表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_categories`
--

DROP TABLE IF EXISTS `activity_categories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_categories` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '分类ID',
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '分类名称(徒步/聚餐/棋牌/唱歌/摄影/太极等)',
  `icon` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分类图标URL',
  `color` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT '#666666' COMMENT '分类标识色',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '排序号(升序)',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_activity_categories_name` (`name`),
  KEY `ix_activity_categories_sort_order` (`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动分类表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_checkins`
--

DROP TABLE IF EXISTS `activity_checkins`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_checkins` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '签到ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '签到用户ID',
  `method` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'qrcode' COMMENT '签到方式: qrcode/manual/auto',
  `checked_in_by` bigint DEFAULT NULL COMMENT '队长用户ID(manual方式时需要)',
  `checked_in_at` datetime NOT NULL COMMENT '签到时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_checkins_activity_id` (`activity_id`),
  KEY `fk_activity_checkins_user_id` (`user_id`),
  KEY `fk_activity_checkins_checked_in_by` (`checked_in_by`),
  CONSTRAINT `fk_activity_checkins_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_checkins_checked_in_by` FOREIGN KEY (`checked_in_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_checkins_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='签到记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_favorites`
--

DROP TABLE IF EXISTS `activity_favorites`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_favorites` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '收藏ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `created_at` datetime NOT NULL COMMENT '收藏时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_activity` (`user_id`,`activity_id`),
  KEY `fk_activity_favorites_activity_id` (`activity_id`),
  CONSTRAINT `fk_activity_favorites_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_favorites_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动收藏表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_ratings`
--

DROP TABLE IF EXISTS `activity_ratings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_ratings` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '评价ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `rating` varchar(5) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '评价: ?/?/?',
  `created_at` datetime NOT NULL COMMENT '评价时间',
  PRIMARY KEY (`id`),
  KEY `fk_activity_ratings_activity_id` (`activity_id`),
  KEY `fk_activity_ratings_user_id` (`user_id`),
  CONSTRAINT `fk_activity_ratings_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_ratings_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动评价表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_reports`
--

DROP TABLE IF EXISTS `activity_reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_reports` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '报告ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID(一对一)',
  `captain_id` bigint NOT NULL COMMENT '队长ID',
  `actual_count` int NOT NULL DEFAULT '0' COMMENT '实到人数',
  `abnormal_count` int NOT NULL DEFAULT '0' COMMENT '异常情况人数',
  `abnormal_details` text COLLATE utf8mb4_unicode_ci COMMENT '异常情况详细说明',
  `photos` text COLLATE utf8mb4_unicode_ci COMMENT '现场照片(JSON数组)',
  `weather_condition` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当时天气情况',
  `notes` text COLLATE utf8mb4_unicode_ci COMMENT '备注/其他说明',
  `submitted_at` datetime DEFAULT NULL COMMENT '提交时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_activity_reports_activity_id` (`activity_id`),
  KEY `ix_activity_reports_captain_id` (`captain_id`),
  CONSTRAINT `fk_activity_reports_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_reports_captain_id` FOREIGN KEY (`captain_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动报告表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_reviews`
--

DROP TABLE IF EXISTS `activity_reviews`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_reviews` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '审核ID',
  `activity_id` bigint NOT NULL COMMENT '被审核活动ID',
  `reviewer_id` bigint NOT NULL COMMENT '审核人(管理员ID)',
  `review_action` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作: approve/reject/flag',
  `review_comment` text COLLATE utf8mb4_unicode_ci COMMENT '审核意见',
  `safety_check_passed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '安全检查是否通过',
  `site_photo_ok` tinyint(1) NOT NULL DEFAULT '0' COMMENT '场地照片是否合规',
  `reviewed_at` datetime NOT NULL COMMENT '审核时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_reviews_activity_id` (`activity_id`),
  KEY `fk_activity_reviews_reviewer_id` (`reviewer_id`),
  CONSTRAINT `fk_activity_reviews_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_reviews_reviewer_id` FOREIGN KEY (`reviewer_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动审核记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_signups`
--

DROP TABLE IF EXISTS `activity_signups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_signups` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '报名记录ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'registered' COMMENT '状态: registered/cancelled/attended/absent',
  `signed_up_at` datetime NOT NULL COMMENT '报名时间',
  `cancelled_at` datetime DEFAULT NULL COMMENT '取消时间',
  `health_confirmed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '活动前是否已确认健康状态',
  `health_confirmed_at` datetime DEFAULT NULL COMMENT '健康确认时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_signups_activity_id` (`activity_id`),
  KEY `ix_activity_signups_user_id` (`user_id`),
  KEY `ix_activity_signups_status` (`status`),
  CONSTRAINT `fk_activity_signups_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_signups_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报名记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_site_photos`
--

DROP TABLE IF EXISTS `activity_site_photos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_site_photos` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '照片ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `image_url` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '照片URL',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '排序号',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_site_photos_activity_id` (`activity_id`),
  CONSTRAINT `fk_activity_site_photos_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动场地照片表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_tag_refs`
--

DROP TABLE IF EXISTS `activity_tag_refs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_tag_refs` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关联ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `tag_id` bigint NOT NULL COMMENT '标签ID',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_activity_tag` (`activity_id`,`tag_id`),
  KEY `fk_activity_tag_refs_tag_id` (`tag_id`),
  CONSTRAINT `fk_activity_tag_refs_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_tag_refs_tag_id` FOREIGN KEY (`tag_id`) REFERENCES `activity_tags` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动标签关联表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_tags`
--

DROP TABLE IF EXISTS `activity_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_tags` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '标签ID',
  `name` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '标签名称(如''新手友好''''可带老伴'')',
  `icon` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '标签图标',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '排序号',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_activity_tags_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动标签字典表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `activity_waitlist`
--

DROP TABLE IF EXISTS `activity_waitlist`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `activity_waitlist` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '候补记录ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `queue_order` int NOT NULL COMMENT '队列序号(从1递增)',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'waiting' COMMENT '状态: waiting/promoted/expired/cancelled',
  `promoted_at` datetime DEFAULT NULL COMMENT '递补成功时间(转为正式报名)',
  `promoted_signup_id` bigint DEFAULT NULL COMMENT '递补生成的报名记录ID',
  `notified_at` datetime DEFAULT NULL COMMENT '通知用户时间',
  `expire_at` datetime DEFAULT NULL COMMENT '递补通知过期时间(超时未响应则顺延)',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_activity_waitlist_activity_id` (`activity_id`),
  KEY `ix_activity_waitlist_user_id` (`user_id`),
  KEY `ix_activity_waitlist_status` (`status`),
  KEY `fk_activity_waitlist_promoted_signup_id` (`promoted_signup_id`),
  CONSTRAINT `fk_activity_waitlist_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_waitlist_promoted_signup_id` FOREIGN KEY (`promoted_signup_id`) REFERENCES `activity_signups` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_activity_waitlist_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='候补队列表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `captain_applications`
--

DROP TABLE IF EXISTS `captain_applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `captain_applications` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '申请ID',
  `user_id` bigint NOT NULL COMMENT '申请人用户ID',
  `real_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '真实姓名',
  `id_card_last4` varchar(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '身份证后4位',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '联系电话',
  `bio` text COLLATE utf8mb4_unicode_ci COMMENT '个人介绍/申请理由',
  `experience` text COLLATE utf8mb4_unicode_ci COMMENT '组织经验',
  `preferred_categories` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '偏好的活动分类ID列表(JSON数组)',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '状态: pending/passed/rejected/suspended',
  `review_comment` text COLLATE utf8mb4_unicode_ci COMMENT '审核意见',
  `reviewed_by` bigint DEFAULT NULL COMMENT '审核人(管理员ID)',
  `reviewed_at` datetime DEFAULT NULL COMMENT '审核时间',
  `training_completed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否完成安全培训',
  `training_completed_at` datetime DEFAULT NULL COMMENT '培训完成时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_captain_applications_user_id` (`user_id`),
  KEY `ix_captain_applications_status` (`status`),
  KEY `fk_captain_applications_reviewed_by` (`reviewed_by`),
  CONSTRAINT `fk_captain_applications_reviewed_by` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_captain_applications_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='队长申请表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `captain_profiles`
--

DROP TABLE IF EXISTS `captain_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `captain_profiles` (
  `user_id` bigint NOT NULL COMMENT '用户ID(一对一)',
  `captain_since` datetime DEFAULT NULL COMMENT '成为队长时间',
  `captain_status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '队长状态: pending/active/suspended/inactive',
  `captain_rating` decimal(2,1) DEFAULT '0.0' COMMENT '队长评分(0.0-5.0)',
  `captain_bio` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '队长介绍/擅长领域',
  `training_completed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否完成安全培训',
  `training_completed_at` datetime DEFAULT NULL COMMENT '培训完成时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  KEY `ix_captain_profiles_captain_status` (`captain_status`),
  CONSTRAINT `fk_captain_profiles_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='队长信息表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `captain_training`
--

DROP TABLE IF EXISTS `captain_training`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `captain_training` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '培训记录ID',
  `user_id` bigint NOT NULL COMMENT '队长用户ID',
  `training_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '培训类型: initial/refresh/special',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '培训内容/材料',
  `score` int DEFAULT NULL COMMENT '考核分数',
  `passed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否通过',
  `trainer` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '培训人(平台工作人员)',
  `passed_at` datetime DEFAULT NULL COMMENT '通过时间',
  `expire_at` datetime DEFAULT NULL COMMENT '有效期(如年审)',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_captain_training_user_id` (`user_id`),
  CONSTRAINT `fk_captain_training_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='队长培训记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_group_members`
--

DROP TABLE IF EXISTS `chat_group_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_group_members` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `group_id` bigint NOT NULL COMMENT '群ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `joined_at` datetime NOT NULL COMMENT '加入时间',
  `last_read_at` datetime DEFAULT NULL COMMENT '最后阅读时间(用于未读计数)',
  `is_muted` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否免打扰',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '退出时间(软删除)',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_group_user` (`group_id`,`user_id`),
  KEY `ix_chat_group_members_group_id` (`group_id`),
  KEY `fk_chat_group_members_user_id` (`user_id`),
  CONSTRAINT `fk_chat_group_members_group_id` FOREIGN KEY (`group_id`) REFERENCES `chat_groups` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_chat_group_members_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群成员表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_groups`
--

DROP TABLE IF EXISTS `chat_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '群ID',
  `activity_id` bigint DEFAULT NULL COMMENT '关联活动ID(一期一对一,预留多对多)',
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '群名称(默认=活动标题)',
  `avatar` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '群头像',
  `captain_id` bigint NOT NULL COMMENT '群主/队长ID',
  `member_count` int NOT NULL DEFAULT '0' COMMENT '当前成员数',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态: active/archived/disabled',
  `archived_at` datetime DEFAULT NULL COMMENT '归档时间(活动结束后48h)',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_chat_groups_activity_id` (`activity_id`),
  KEY `ix_chat_groups_captain_id` (`captain_id`),
  KEY `ix_chat_groups_status` (`status`),
  CONSTRAINT `fk_chat_groups_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_chat_groups_captain_id` FOREIGN KEY (`captain_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群聊表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_messages`
--

DROP TABLE IF EXISTS `chat_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_messages` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `group_id` bigint NOT NULL COMMENT '群ID',
  `sender_id` bigint NOT NULL COMMENT '发送者ID',
  `msg_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'text' COMMENT '消息类型: text/voice/image/system',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '消息内容(text/voice转文字)',
  `voice_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '语音文件URL',
  `voice_duration` int DEFAULT NULL COMMENT '语音时长(秒)',
  `image_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '图片URL',
  `is_announcement` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否队长置顶公告',
  `created_at` datetime NOT NULL COMMENT '发送时间',
  PRIMARY KEY (`id`),
  KEY `ix_chat_messages_group_id` (`group_id`),
  KEY `ix_chat_messages_created_at` (`created_at`),
  KEY `fk_chat_messages_sender_id` (`sender_id`),
  CONSTRAINT `fk_chat_messages_group_id` FOREIGN KEY (`group_id`) REFERENCES `chat_groups` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_chat_messages_sender_id` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群消息表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `health_declarations`
--

DROP TABLE IF EXISTS `health_declarations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `health_declarations` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '声明ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `health_status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'good' COMMENT '状态: good/unwell/decline',
  `note` text COLLATE utf8mb4_unicode_ci COMMENT '备注(如身体不适的具体情况)',
  `declared_at` datetime NOT NULL COMMENT '确认时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_health_declarations_user_id` (`user_id`),
  KEY `ix_health_declarations_activity_id` (`activity_id`),
  CONSTRAINT `fk_health_declarations_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_health_declarations_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康声明记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `insurance_records`
--

DROP TABLE IF EXISTS `insurance_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `insurance_records` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '保险记录ID',
  `activity_id` bigint NOT NULL COMMENT '活动ID',
  `user_id` bigint NOT NULL COMMENT '被保人用户ID',
  `policy_no` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '保单号',
  `provider` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '保险公司',
  `coverage` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '保障范围说明',
  `premium` decimal(10,2) NOT NULL DEFAULT '1.00' COMMENT '保费(元/人/天)',
  `insured_date` date NOT NULL COMMENT '投保日期(活动日期)',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态: active/claimed/expired',
  `claim_no` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '理赔单号',
  `claimed_at` datetime DEFAULT NULL COMMENT '理赔时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `ix_insurance_records_activity_id` (`activity_id`),
  KEY `ix_insurance_records_policy_no` (`policy_no`),
  KEY `fk_insurance_records_user_id` (`user_id`),
  CONSTRAINT `fk_insurance_records_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_insurance_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='保险记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '通知ID',
  `user_id` bigint NOT NULL COMMENT '接收用户ID',
  `type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '类型: activity_reminder/safety_alert/system/activity_update/chat',
  `title` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '通知标题',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '通知内容',
  `ref_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '关联对象类型: activity/chat_group/system',
  `ref_id` bigint DEFAULT NULL COMMENT '关联对象ID',
  `is_read` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否已读',
  `read_at` datetime DEFAULT NULL COMMENT '读取时间',
  `channel` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'in_app' COMMENT '推送渠道: in_app/sms/wechat_template',
  `sent_at` datetime DEFAULT NULL COMMENT '推送时间',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_notifications_user_id` (`user_id`),
  KEY `ix_notifications_type` (`type`),
  KEY `ix_notifications_is_read` (`is_read`),
  CONSTRAINT `fk_notifications_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `operation_logs`
--

DROP TABLE IF EXISTS `operation_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `operation_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '日志ID',
  `operator_id` bigint NOT NULL COMMENT '操作人ID',
  `action` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型: create_activity/approve/reject/suspend_captain/...',
  `target_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作对象类型: activity/user/captain_app/review',
  `target_id` bigint DEFAULT NULL COMMENT '操作对象ID',
  `detail` text COLLATE utf8mb4_unicode_ci COMMENT '操作详情(JSON格式)',
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '操作人IP地址',
  `created_at` datetime NOT NULL COMMENT '操作时间',
  PRIMARY KEY (`id`),
  KEY `ix_operation_logs_operator_id` (`operator_id`),
  KEY `ix_operation_logs_action` (`action`),
  CONSTRAINT `fk_operation_logs_operator_id` FOREIGN KEY (`operator_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `partner_profiles`
--

DROP TABLE IF EXISTS `partner_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `partner_profiles` (
  `user_id` bigint NOT NULL COMMENT '用户ID(一对一)',
  `partner_street` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '合作街道名称',
  `partner_contact` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '街道对接人',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_partner_profiles_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='合作方信息表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `partner_streets`
--

DROP TABLE IF EXISTS `partner_streets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `partner_streets` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '街道ID',
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '街道/社区名称',
  `city` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所在城市',
  `district` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '所在区县',
  `address` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '办公地址',
  `contact_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '对接人姓名',
  `contact_phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '对接人电话',
  `contact_position` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '对接人职务',
  `venues` text COLLATE utf8mb4_unicode_ci COMMENT '可用场地列表(JSON数组: [{name, address, capacity, photos}])',
  `agreement_start` date DEFAULT NULL COMMENT '合作协议开始日期',
  `agreement_end` date DEFAULT NULL COMMENT '合作协议结束日期',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态: active/inactive/pending',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_partner_streets_city` (`city`),
  KEY `ix_partner_streets_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='街道合作方表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payment_records`
--

DROP TABLE IF EXISTS `payment_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_records` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '支付记录ID',
  `signup_id` bigint NOT NULL COMMENT '关联报名记录ID',
  `user_id` bigint NOT NULL COMMENT '付款用户ID',
  `activity_id` bigint NOT NULL COMMENT '关联活动ID',
  `amount` decimal(10,2) NOT NULL COMMENT '支付金额(元)',
  `refund_amount` decimal(10,2) DEFAULT '0.00' COMMENT '已退款金额',
  `payment_method` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '支付方式: wechat/alipay/balance/free',
  `channel_order_id` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '支付平台订单号(微信/支付宝单号)',
  `channel_trade_no` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '支付平台交易号',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT '状态: pending/success/failed/refunding/refunded/closed',
  `paid_at` datetime DEFAULT NULL COMMENT '支付成功时间',
  `refunded_at` datetime DEFAULT NULL COMMENT '退款完成时间',
  `refund_reason` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '退款原因',
  `expire_at` datetime DEFAULT NULL COMMENT '支付过期时间(超时未付自动取消)',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段(支付回调原始数据等)',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_payment_records_signup_id` (`signup_id`),
  KEY `ix_payment_records_user_id` (`user_id`),
  KEY `ix_payment_records_activity_id` (`activity_id`),
  KEY `ix_payment_records_channel_order_id` (`channel_order_id`),
  KEY `ix_payment_records_status` (`status`),
  CONSTRAINT `fk_payment_records_activity_id` FOREIGN KEY (`activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_payment_records_signup_id` FOREIGN KEY (`signup_id`) REFERENCES `activity_signups` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_payment_records_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支付记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `premium_subscriptions`
--

DROP TABLE IF EXISTS `premium_subscriptions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `premium_subscriptions` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '订阅ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `plan_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '方案: monthly/quarterly/yearly',
  `start_date` datetime NOT NULL COMMENT '生效时间',
  `end_date` datetime NOT NULL COMMENT '到期时间',
  `auto_renew` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否自动续费',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态: active/expired/cancelled/pending',
  `payment_method` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '支付方式: wechat/alipay',
  `payment_id` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '支付平台订单号',
  `amount` decimal(10,2) NOT NULL COMMENT '支付金额',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_premium_subscriptions_user_id` (`user_id`),
  KEY `ix_premium_subscriptions_status` (`status`),
  CONSTRAINT `fk_premium_subscriptions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订阅付费表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `regions`
--

DROP TABLE IF EXISTS `regions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `regions` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `code` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '行政区划代码(GB/T 2260)，如 110000=北京, 110101=东城区',
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '行政区划名称',
  `parent_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '父级代码(省→市→区县)',
  `level` int NOT NULL COMMENT '级别: 1=省/直辖市 2=地级市 3=区县',
  `pinyin` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '拼音全拼(支持拼音搜索)',
  `short_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '简称(如: 北京→京)',
  `is_active` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否启用(有些新区划可能暂未开通服务)',
  `ext_data` json DEFAULT NULL COMMENT '拓展字段(经纬度边界等)',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_regions_code` (`code`),
  KEY `ix_regions_parent_code` (`parent_code`),
  KEY `ix_regions_level` (`level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='行政区划表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system_config`
--

DROP TABLE IF EXISTS `system_config`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_config` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '配置ID',
  `config_key` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '配置键名',
  `config_value` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '配置值(JSON或字符串)',
  `config_group` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'general' COMMENT '分组: safety/general/notification/premium',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '配置说明',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_system_config_config_key` (`config_key`),
  KEY `ix_system_config_config_group` (`config_group`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_auth`
--

DROP TABLE IF EXISTS `user_auth`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_auth` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '认证记录ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `auth_type` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '认证类型: password/wx_openid/wx_unionid/apple',
  `auth_value` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '认证凭据(密码hash或openid)',
  `verified_at` datetime DEFAULT NULL COMMENT '验证通过时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_user_auth_user_id` (`user_id`),
  CONSTRAINT `fk_user_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户认证表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_friends`
--

DROP TABLE IF EXISTS `user_friends`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_friends` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '关系ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `friend_id` bigint NOT NULL COMMENT '好友ID',
  `source` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'activity' COMMENT '来源: activity/manual/interest',
  `source_activity_id` bigint DEFAULT NULL COMMENT '来源活动ID(活动认识的好友)',
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT '状态: active/blocked',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_friendship` (`user_id`,`friend_id`),
  KEY `fk_user_friends_friend_id` (`friend_id`),
  KEY `fk_user_friends_source_activity_id` (`source_activity_id`),
  CONSTRAINT `fk_user_friends_friend_id` FOREIGN KEY (`friend_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_friends_source_activity_id` FOREIGN KEY (`source_activity_id`) REFERENCES `activities` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_friends_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='好友关系表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_identities`
--

DROP TABLE IF EXISTS `user_identities`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_identities` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '实名记录ID',
  `user_id` bigint NOT NULL COMMENT '用户ID',
  `identity_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '证件类型: id_card/passport/hk_id/tw_comp',
  `identity_hash` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '证件全文SHA-256（不可逆，用于去重校验）',
  `identity_enc` blob COMMENT 'AES-256加密存储（需要时可解密，如保险报案）',
  `identity_last4` varchar(4) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '明文后4位(展示用)',
  `verified_at` datetime DEFAULT NULL COMMENT '实名认证通过时间',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `ix_user_identities_user_id` (`user_id`),
  CONSTRAINT `fk_user_identities_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户实名表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_private_messages`
--

DROP TABLE IF EXISTS `user_private_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_private_messages` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `sender_id` bigint NOT NULL COMMENT '发送者ID',
  `receiver_id` bigint NOT NULL COMMENT '接收者ID',
  `msg_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'text' COMMENT '类型: text/image/voice',
  `content` text COLLATE utf8mb4_unicode_ci COMMENT '消息内容',
  `is_read` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否已读',
  `read_at` datetime DEFAULT NULL COMMENT '读取时间',
  `created_at` datetime NOT NULL COMMENT '发送时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  KEY `ix_user_private_messages_sender_id` (`sender_id`),
  KEY `ix_user_private_messages_receiver_id` (`receiver_id`),
  CONSTRAINT `fk_user_private_messages_receiver_id` FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_private_messages_sender_id` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_profiles`
--

DROP TABLE IF EXISTS `user_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_profiles` (
  `user_id` bigint NOT NULL COMMENT '用户ID(一对一)',
  `real_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '真实姓名',
  `gender` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '性别: male/female/unknown',
  `birth_year` int DEFAULT NULL COMMENT '出生年份',
  `city` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所在城市(展示用)',
  `district` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所在区县(展示用)',
  `province_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '省份代码(预留)',
  `city_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '城市代码(预留)',
  `district_code` varchar(12) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '区县代码(预留)',
  `bio` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '个人简介',
  `interests` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '兴趣标签(逗号分隔)',
  `ghost_mode` tinyint(1) NOT NULL DEFAULT '0' COMMENT '隐身模式',
  `allow_private_msg` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否允许私信',
  `allow_profile_view` tinyint(1) NOT NULL DEFAULT '1' COMMENT '是否允许他人查看资料',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  KEY `ix_user_profiles_birth_year` (`birth_year`),
  KEY `ix_user_profiles_city` (`city`),
  KEY `fk_user_profiles_province_code` (`province_code`),
  KEY `fk_user_profiles_city_code` (`city_code`),
  KEY `fk_user_profiles_district_code` (`district_code`),
  CONSTRAINT `fk_user_profiles_city_code` FOREIGN KEY (`city_code`) REFERENCES `regions` (`code`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_profiles_district_code` FOREIGN KEY (`district_code`) REFERENCES `regions` (`code`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_profiles_province_code` FOREIGN KEY (`province_code`) REFERENCES `regions` (`code`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_user_profiles_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户资料表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_safety`
--

DROP TABLE IF EXISTS `user_safety`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_safety` (
  `user_id` bigint NOT NULL COMMENT '用户ID(一对一)',
  `emergency_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '紧急联系人姓名',
  `emergency_phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '紧急联系人电话',
  `emergency_relation` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '与紧急联系人的关系',
  `emergency_confirmed` tinyint(1) NOT NULL DEFAULT '0' COMMENT '紧急联系人是否已短信确认',
  `has_chronic_disease` tinyint(1) DEFAULT NULL COMMENT '是否有慢性病',
  `chronic_disease_note` text COLLATE utf8mb4_unicode_ci COMMENT '慢性病说明',
  `guarantor_name` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '75岁以上担保人姓名',
  `guarantor_phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '担保人电话',
  `guarantor_confirmed` tinyint(1) DEFAULT '0' COMMENT '担保人是否已确认',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  CONSTRAINT `fk_user_safety_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户安全信息表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_stats`
--

DROP TABLE IF EXISTS `user_stats`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_stats` (
  `user_id` bigint NOT NULL COMMENT '用户ID(一对一)',
  `vitality` int NOT NULL DEFAULT '0' COMMENT '活力值(只增不减，非货币)',
  `activity_count` int NOT NULL DEFAULT '0' COMMENT '参加活动总次数(高频写)',
  `activity_streak` int NOT NULL DEFAULT '0' COMMENT '连续活跃月数',
  `friends_count` int NOT NULL DEFAULT '0' COMMENT '好友数',
  `last_active_at` datetime DEFAULT NULL COMMENT '最后活跃时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  KEY `ix_user_stats_last_active_at` (`last_active_at`),
  CONSTRAINT `fk_user_stats_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户统计表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '手机号（登录账号，全局唯一）',
  `nickname` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户昵称',
  `avatar_url` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '头像URL',
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user' COMMENT '角色: user/captain/admin/partner',
  `is_banned` tinyint(1) NOT NULL DEFAULT '0' COMMENT '是否封禁',
  `version` int NOT NULL DEFAULT '1' COMMENT '乐观锁版本号',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_phone` (`phone`),
  KEY `ix_users_role` (`role`),
  KEY `ix_users_deleted_at` (`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户核心表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-06-03 22:22:04
