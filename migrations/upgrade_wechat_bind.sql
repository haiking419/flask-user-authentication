-- 企业微信绑定功能数据库升级脚本

-- 检查并添加企业微信用户ID字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_schema = DATABASE() 
    AND table_name = 'users' 
    AND column_name = 'wechat_corp_userid'
);

IF @column_exists = 0 THEN
    ALTER TABLE users 
    ADD COLUMN wechat_corp_userid VARCHAR(100) NULL COMMENT '企业微信用户ID';
    
    -- 添加索引提高查询效率
    CREATE INDEX idx_wechat_corp_userid ON users(wechat_corp_userid);
    
    SELECT '已添加企业微信用户ID字段' AS result;
ELSE
    SELECT '企业微信用户ID字段已存在' AS result;
END IF;

-- 检查并添加企业微信用户名称字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_schema = DATABASE() 
    AND table_name = 'users' 
    AND column_name = 'wechat_corp_name'
);

IF @column_exists = 0 THEN
    ALTER TABLE users 
    ADD COLUMN wechat_corp_name VARCHAR(200) NULL COMMENT '企业微信用户名称';
    SELECT '已添加企业微信用户名称字段' AS result;
ELSE
    SELECT '企业微信用户名称字段已存在' AS result;
END IF;

-- 检查并添加企业微信头像URL字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_schema = DATABASE() 
    AND table_name = 'users' 
    AND column_name = 'wechat_corp_avatar'
);

IF @column_exists = 0 THEN
    ALTER TABLE users 
    ADD COLUMN wechat_corp_avatar VARCHAR(500) NULL COMMENT '企业微信用户头像URL';
    SELECT '已添加企业微信头像URL字段' AS result;
ELSE
    SELECT '企业微信头像URL字段已存在' AS result;
END IF;

-- 检查并添加最后登录时间字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_schema = DATABASE() 
    AND table_name = 'users' 
    AND column_name = 'last_login_time'
);

IF @column_exists = 0 THEN
    ALTER TABLE users 
    ADD COLUMN last_login_time DATETIME NULL COMMENT '最后登录时间';
    SELECT '已添加最后登录时间字段' AS result;
ELSE
    SELECT '最后登录时间字段已存在' AS result;
END IF;

-- 检查并添加登录类型字段（如果不存在）
SET @column_exists = (
    SELECT COUNT(*) 
    FROM information_schema.columns 
    WHERE table_schema = DATABASE() 
    AND table_name = 'users' 
    AND column_name = 'login_type'
);

IF @column_exists = 0 THEN
    ALTER TABLE users 
    ADD COLUMN login_type VARCHAR(50) NULL COMMENT '登录类型（password/wechat_corp）';
    SELECT '已添加登录类型字段' AS result;
ELSE
    SELECT '登录类型字段已存在' AS result;
END IF;