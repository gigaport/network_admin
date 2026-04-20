-- ================================================================
-- 네트워크 관리 시스템 데이터베이스 스키마 DDL
-- 생성일: 2026-04-07
-- 설명: FastAPI 라우터 및 마이그레이션 스크립트 분석을 통해 생성
-- ================================================================

-- ================================================================
-- 1. 회원사 코드 테이블 (subscriber_codes)
-- 설명: 회원사 및 정보이용사 코드 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS subscriber_codes (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) UNIQUE NOT NULL,
    member_number INTEGER UNIQUE NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    subscription_type VARCHAR(50) NOT NULL,
    is_pb BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_subscriber_codes_member_code ON subscriber_codes(member_code);
CREATE INDEX IF NOT EXISTS idx_subscriber_codes_member_number ON subscriber_codes(member_number);
CREATE INDEX IF NOT EXISTS idx_subscriber_codes_company_name ON subscriber_codes(company_name);

COMMENT ON TABLE subscriber_codes IS '회원사 및 정보이용사 코드 정보';
COMMENT ON COLUMN subscriber_codes.member_code IS '회원사 코드 (예: HY, BK, NE 등)';
COMMENT ON COLUMN subscriber_codes.member_number IS '회원사 넘버 (정렬용)';
COMMENT ON COLUMN subscriber_codes.company_name IS '회사명';
COMMENT ON COLUMN subscriber_codes.subscription_type IS '가입 유형';
COMMENT ON COLUMN subscriber_codes.is_pb IS 'PB 여부';


-- ================================================================
-- 2. 고객 주소 테이블 (customer_addresses)
-- 설명: 회원사별 데이터센터 주소 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS customer_addresses (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(50) NOT NULL,
    post_code VARCHAR(10),
    main_address VARCHAR(200),
    detailed_address VARCHAR(200),
    summary_address VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(member_code, datacenter_code),
    FOREIGN KEY (member_code) REFERENCES subscriber_codes(member_code) ON DELETE CASCADE
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_customer_addresses_member_code ON customer_addresses(member_code);
CREATE INDEX IF NOT EXISTS idx_customer_addresses_datacenter_code ON customer_addresses(datacenter_code);

COMMENT ON TABLE customer_addresses IS '회원사별 데이터센터 주소 정보';
COMMENT ON COLUMN customer_addresses.datacenter_code IS '데이터센터 코드 (예: PB_메인, PB_DR, DR 등)';
COMMENT ON COLUMN customer_addresses.summary_address IS '요약 주소 (필수)';


-- ================================================================
-- 3. 시세 상품 마스터 테이블 (sise_products)
-- 설명: 시세 상품 정보 (정규화된 테이블)
-- ================================================================
CREATE TABLE IF NOT EXISTS sise_products (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(50) NOT NULL UNIQUE,
    line_speed VARCHAR(20),
    data_format VARCHAR(20),
    operation_ip1 VARCHAR(20),
    operation_ip2 VARCHAR(20),
    test_ip VARCHAR(20),
    dr_ip VARCHAR(20),
    retransmit_port VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_sise_products_product_name ON sise_products(product_name);

COMMENT ON TABLE sise_products IS '시세 상품 마스터 정보';
COMMENT ON COLUMN sise_products.product_name IS '상품명 (고유값)';
COMMENT ON COLUMN sise_products.line_speed IS '회선 속도';
COMMENT ON COLUMN sise_products.data_format IS '데이터 포맷';
COMMENT ON COLUMN sise_products.operation_ip1 IS '운영 IP 1';
COMMENT ON COLUMN sise_products.operation_ip2 IS '운영 IP 2';
COMMENT ON COLUMN sise_products.test_ip IS '테스트 IP';
COMMENT ON COLUMN sise_products.dr_ip IS 'DR IP';
COMMENT ON COLUMN sise_products.retransmit_port IS '재전송 포트';


-- ================================================================
-- 4. 시세 채널 정보 테이블 (sise_channels)
-- 설명: 시세 상품별 채널 정보 (정규화된 테이블)
-- ================================================================
CREATE TABLE IF NOT EXISTS sise_channels (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    service_type VARCHAR(50),
    market_type VARCHAR(20),
    multicast_group_ip VARCHAR(20),
    operation_port VARCHAR(10),
    test_port VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, service_type, market_type),
    FOREIGN KEY (product_id) REFERENCES sise_products(id) ON DELETE CASCADE
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_sise_channels_product_id ON sise_channels(product_id);
CREATE INDEX IF NOT EXISTS idx_sise_channels_service_type ON sise_channels(service_type);
CREATE INDEX IF NOT EXISTS idx_sise_channels_market_type ON sise_channels(market_type);

COMMENT ON TABLE sise_channels IS '시세 상품별 채널 정보';
COMMENT ON COLUMN sise_channels.product_id IS '시세 상품 ID (외래키)';
COMMENT ON COLUMN sise_channels.service_type IS '서비스 유형';
COMMENT ON COLUMN sise_channels.market_type IS '시장 유형';
COMMENT ON COLUMN sise_channels.multicast_group_ip IS '멀티캐스트 그룹 IP';


-- ================================================================
-- 5. 회원사 요금 스케줄 테이블 (member_fee_schedule)
-- 설명: 회원사 과금 기준 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS member_fee_schedule (
    id SERIAL PRIMARY KEY,
    fee_code VARCHAR(50) UNIQUE NOT NULL,
    usage VARCHAR(100),
    description VARCHAR(200),
    price INTEGER DEFAULT 0,
    phase INTEGER DEFAULT 0,
    bandwidth VARCHAR(50),
    additional_circuit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_member_fee_schedule_fee_code ON member_fee_schedule(fee_code);
CREATE INDEX IF NOT EXISTS idx_member_fee_schedule_usage ON member_fee_schedule(usage);

COMMENT ON TABLE member_fee_schedule IS '회원사 과금 기준 정보';
COMMENT ON COLUMN member_fee_schedule.fee_code IS '요금 코드 (고유값)';
COMMENT ON COLUMN member_fee_schedule.usage IS '용도';
COMMENT ON COLUMN member_fee_schedule.description IS '설명';
COMMENT ON COLUMN member_fee_schedule.price IS '가격';
COMMENT ON COLUMN member_fee_schedule.phase IS '단계';
COMMENT ON COLUMN member_fee_schedule.bandwidth IS '대역폭';
COMMENT ON COLUMN member_fee_schedule.additional_circuit IS '추가 회선 여부';


-- ================================================================
-- 6. 정보이용사 요금 스케줄 테이블 (info_fee_schedule)
-- 설명: 정보이용사 과금 기준 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS info_fee_schedule (
    id SERIAL PRIMARY KEY,
    fee_code VARCHAR(50) UNIQUE NOT NULL,
    usage VARCHAR(100),
    description VARCHAR(200),
    price INTEGER DEFAULT 0,
    phase INTEGER DEFAULT 0,
    bandwidth VARCHAR(50),
    additional_circuit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_info_fee_schedule_fee_code ON info_fee_schedule(fee_code);
CREATE INDEX IF NOT EXISTS idx_info_fee_schedule_usage ON info_fee_schedule(usage);

COMMENT ON TABLE info_fee_schedule IS '정보이용사 과금 기준 정보';
COMMENT ON COLUMN info_fee_schedule.fee_code IS '요금 코드 (고유값)';
COMMENT ON COLUMN info_fee_schedule.usage IS '용도';
COMMENT ON COLUMN info_fee_schedule.description IS '설명';
COMMENT ON COLUMN info_fee_schedule.price IS '가격';
COMMENT ON COLUMN info_fee_schedule.phase IS '단계';
COMMENT ON COLUMN info_fee_schedule.bandwidth IS '대역폭';
COMMENT ON COLUMN info_fee_schedule.additional_circuit IS '추가 회선 여부';


-- ================================================================
-- 7. 네트워크 원가 정보 테이블 (network_cost)
-- 설명: 통신사별 회선 원가 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS network_cost (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    circuit_type VARCHAR(50),
    cost_standart VARCHAR(100) NOT NULL,
    cost_price INTEGER DEFAULT 0,
    description VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, circuit_type, cost_standart)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_network_cost_code ON network_cost(code);
CREATE INDEX IF NOT EXISTS idx_network_cost_provider ON network_cost(provider);
CREATE INDEX IF NOT EXISTS idx_network_cost_circuit_type ON network_cost(circuit_type);

COMMENT ON TABLE network_cost IS '통신사별 회선 원가 정보';
COMMENT ON COLUMN network_cost.code IS '원가 코드 (고유값, 예: KTC-M-001, LGU-M-006)';
COMMENT ON COLUMN network_cost.provider IS '통신사 (예: KTC, LGU)';
COMMENT ON COLUMN network_cost.circuit_type IS '회선 유형';
COMMENT ON COLUMN network_cost.cost_standart IS '비용 기준';
COMMENT ON COLUMN network_cost.cost_price IS '원가';


-- ================================================================
-- 8. 회원사 회선 정보 테이블 (circuit)
-- 설명: 회원사 회선 상세 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS circuit (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(50) NOT NULL,
    gubn VARCHAR(50),
    side_a VARCHAR(100),
    provider VARCHAR(50),
    circuit_id VARCHAR(100),
    nni_id VARCHAR(100),
    type VARCHAR(50),
    state VARCHAR(50),
    env VARCHAR(50),
    usage VARCHAR(100),
    product VARCHAR(100),
    bandwidth VARCHAR(50),
    additional_circuit BOOLEAN DEFAULT FALSE,
    cot_device VARCHAR(100),
    rt_device VARCHAR(100),
    lldp_cot_device VARCHAR(100),
    lldp_port VARCHAR(100),
    lldp_rt_device VARCHAR(100),
    lldp_rt_port VARCHAR(100),
    join_type INTEGER DEFAULT 0,
    contract_date DATE,
    expiry_date DATE,
    contract_period VARCHAR(50),
    report_number VARCHAR(100),
    comments TEXT,
    phase INTEGER DEFAULT 0,
    fee_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_code) REFERENCES subscriber_codes(member_code) ON DELETE CASCADE,
    FOREIGN KEY (fee_code) REFERENCES member_fee_schedule(fee_code) ON DELETE SET NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_circuit_member_code ON circuit(member_code);
CREATE INDEX IF NOT EXISTS idx_circuit_datacenter_code ON circuit(datacenter_code);
CREATE INDEX IF NOT EXISTS idx_circuit_provider ON circuit(provider);
CREATE INDEX IF NOT EXISTS idx_circuit_circuit_id ON circuit(circuit_id);
CREATE INDEX IF NOT EXISTS idx_circuit_nni_id ON circuit(nni_id);
CREATE INDEX IF NOT EXISTS idx_circuit_fee_code ON circuit(fee_code);
CREATE INDEX IF NOT EXISTS idx_circuit_state ON circuit(state);

COMMENT ON TABLE circuit IS '회원사 회선 상세 정보';
COMMENT ON COLUMN circuit.member_code IS '회원사 코드';
COMMENT ON COLUMN circuit.datacenter_code IS '데이터센터 코드';
COMMENT ON COLUMN circuit.gubn IS '구분';
COMMENT ON COLUMN circuit.side_a IS 'Side A';
COMMENT ON COLUMN circuit.provider IS '통신사';
COMMENT ON COLUMN circuit.circuit_id IS '회선 ID';
COMMENT ON COLUMN circuit.nni_id IS 'NNI ID';
COMMENT ON COLUMN circuit.type IS '유형';
COMMENT ON COLUMN circuit.state IS '상태';
COMMENT ON COLUMN circuit.env IS '환경 (운영/테스트)';
COMMENT ON COLUMN circuit.usage IS '용도';
COMMENT ON COLUMN circuit.product IS '상품';
COMMENT ON COLUMN circuit.bandwidth IS '대역폭';
COMMENT ON COLUMN circuit.additional_circuit IS '추가 회선 여부';
COMMENT ON COLUMN circuit.cot_device IS 'COT 장비';
COMMENT ON COLUMN circuit.rt_device IS 'RT 장비';
COMMENT ON COLUMN circuit.lldp_cot_device IS 'LLDP COT 장비';
COMMENT ON COLUMN circuit.lldp_port IS 'LLDP 포트';
COMMENT ON COLUMN circuit.lldp_rt_device IS 'LLDP RT 장비';
COMMENT ON COLUMN circuit.lldp_rt_port IS 'LLDP RT 포트';
COMMENT ON COLUMN circuit.join_type IS '가입 유형 (0: 일반)';
COMMENT ON COLUMN circuit.contract_date IS '계약일';
COMMENT ON COLUMN circuit.expiry_date IS '만료일';
COMMENT ON COLUMN circuit.contract_period IS '계약 기간';
COMMENT ON COLUMN circuit.report_number IS '보고서 번호';
COMMENT ON COLUMN circuit.comments IS '코멘트';
COMMENT ON COLUMN circuit.phase IS '단계';
COMMENT ON COLUMN circuit.fee_code IS '요금 코드 (외래키)';


-- ================================================================
-- 9. 정보이용사 회선 정보 테이블 (info_company_circuit)
-- 설명: 정보이용사 회선 상세 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS info_company_circuit (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(50) NOT NULL,
    gubn VARCHAR(50),
    side_a VARCHAR(100),
    provider VARCHAR(50),
    circuit_id VARCHAR(100),
    type VARCHAR(50),
    env VARCHAR(50),
    usage VARCHAR(100),
    product VARCHAR(100),
    bandwidth VARCHAR(50),
    additional_circuit BOOLEAN DEFAULT FALSE,
    lldp_port VARCHAR(100),
    join_type INTEGER DEFAULT 0,
    contract_date DATE,
    expiry_date DATE,
    contract_period VARCHAR(50),
    report_number VARCHAR(100),
    comments TEXT,
    phase INTEGER DEFAULT 0,
    fee_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_code) REFERENCES subscriber_codes(member_code) ON DELETE CASCADE,
    FOREIGN KEY (fee_code) REFERENCES info_fee_schedule(fee_code) ON DELETE SET NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_info_company_circuit_member_code ON info_company_circuit(member_code);
CREATE INDEX IF NOT EXISTS idx_info_company_circuit_datacenter_code ON info_company_circuit(datacenter_code);
CREATE INDEX IF NOT EXISTS idx_info_company_circuit_provider ON info_company_circuit(provider);
CREATE INDEX IF NOT EXISTS idx_info_company_circuit_circuit_id ON info_company_circuit(circuit_id);
CREATE INDEX IF NOT EXISTS idx_info_company_circuit_fee_code ON info_company_circuit(fee_code);

COMMENT ON TABLE info_company_circuit IS '정보이용사 회선 상세 정보';
COMMENT ON COLUMN info_company_circuit.member_code IS '정보이용사 코드';
COMMENT ON COLUMN info_company_circuit.datacenter_code IS '데이터센터 코드';


-- ================================================================
-- 10. 회원사 매입 계약 테이블 (purchase_contract)
-- 설명: 회원사 회선 매입 계약 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS purchase_contract (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(50),
    provider VARCHAR(50),
    billing_start_date DATE,
    contract_end_date DATE,
    service_id VARCHAR(100),
    nni_id VARCHAR(100),
    cost_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_code) REFERENCES subscriber_codes(member_code) ON DELETE CASCADE,
    FOREIGN KEY (cost_code) REFERENCES network_cost(code) ON DELETE SET NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_purchase_contract_member_code ON purchase_contract(member_code);
CREATE INDEX IF NOT EXISTS idx_purchase_contract_datacenter_code ON purchase_contract(datacenter_code);
CREATE INDEX IF NOT EXISTS idx_purchase_contract_provider ON purchase_contract(provider);
CREATE INDEX IF NOT EXISTS idx_purchase_contract_cost_code ON purchase_contract(cost_code);
CREATE INDEX IF NOT EXISTS idx_purchase_contract_nni_id ON purchase_contract(nni_id);

COMMENT ON TABLE purchase_contract IS '회원사 회선 매입 계약 정보';
COMMENT ON COLUMN purchase_contract.member_code IS '회원사 코드';
COMMENT ON COLUMN purchase_contract.datacenter_code IS '데이터센터 코드';
COMMENT ON COLUMN purchase_contract.provider IS '통신사';
COMMENT ON COLUMN purchase_contract.billing_start_date IS '청구 시작일';
COMMENT ON COLUMN purchase_contract.contract_end_date IS '계약 종료일';
COMMENT ON COLUMN purchase_contract.service_id IS '서비스 ID';
COMMENT ON COLUMN purchase_contract.nni_id IS 'NNI ID';
COMMENT ON COLUMN purchase_contract.cost_code IS '원가 코드 (외래키)';


-- ================================================================
-- 11. 정보이용사 매입 계약 테이블 (info_purchase_contract)
-- 설명: 정보이용사 회선 매입 계약 정보
-- ================================================================
CREATE TABLE IF NOT EXISTS info_purchase_contract (
    id SERIAL PRIMARY KEY,
    member_code VARCHAR(10) NOT NULL,
    datacenter_code VARCHAR(50),
    provider VARCHAR(50),
    billing_start_date DATE,
    contract_end_date DATE,
    service_id VARCHAR(100),
    nni_id VARCHAR(100),
    cost_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_code) REFERENCES subscriber_codes(member_code) ON DELETE CASCADE,
    FOREIGN KEY (cost_code) REFERENCES network_cost(code) ON DELETE SET NULL
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_info_purchase_contract_member_code ON info_purchase_contract(member_code);
CREATE INDEX IF NOT EXISTS idx_info_purchase_contract_datacenter_code ON info_purchase_contract(datacenter_code);
CREATE INDEX IF NOT EXISTS idx_info_purchase_contract_provider ON info_purchase_contract(provider);
CREATE INDEX IF NOT EXISTS idx_info_purchase_contract_cost_code ON info_purchase_contract(cost_code);
CREATE INDEX IF NOT EXISTS idx_info_purchase_contract_nni_id ON info_purchase_contract(nni_id);

COMMENT ON TABLE info_purchase_contract IS '정보이용사 회선 매입 계약 정보';
COMMENT ON COLUMN info_purchase_contract.member_code IS '정보이용사 코드';
COMMENT ON COLUMN info_purchase_contract.datacenter_code IS '데이터센터 코드';
COMMENT ON COLUMN info_purchase_contract.provider IS '통신사';
COMMENT ON COLUMN info_purchase_contract.billing_start_date IS '청구 시작일';
COMMENT ON COLUMN info_purchase_contract.contract_end_date IS '계약 종료일';
COMMENT ON COLUMN info_purchase_contract.service_id IS '서비스 ID';
COMMENT ON COLUMN info_purchase_contract.nni_id IS 'NNI ID';
COMMENT ON COLUMN info_purchase_contract.cost_code IS '원가 코드 (외래키)';


-- ================================================================
-- 12. 네트워크 계약 테이블 (network_contracts)
-- 설명: 네트워크 계약 진행 상황 관리
-- ================================================================
CREATE TABLE IF NOT EXISTS network_contracts (
    id SERIAL PRIMARY KEY,
    번호 VARCHAR(50),
    key_code VARCHAR(100),
    지역 VARCHAR(100),
    유형 VARCHAR(50),
    회원사명 VARCHAR(100),
    회선분류 VARCHAR(50),
    계약유형 VARCHAR(50),
    안내 VARCHAR(20),
    내부검토 VARCHAR(20),
    계약착수 VARCHAR(20),
    날인대기 VARCHAR(20),
    계약완료 VARCHAR(20),
    완료보고문서번호 VARCHAR(100),
    계약체결일 DATE,
    추가체결일 DATE,
    약정기간 VARCHAR(50),
    약정만료일 DATE,
    계약금액 VARCHAR(100),
    추가신청금액 VARCHAR(100),
    계약금액합계 VARCHAR(100),
    비고 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_network_contracts_회원사명 ON network_contracts(회원사명);
CREATE INDEX IF NOT EXISTS idx_network_contracts_계약유형 ON network_contracts(계약유형);
CREATE INDEX IF NOT EXISTS idx_network_contracts_key_code ON network_contracts(key_code);

COMMENT ON TABLE network_contracts IS '네트워크 계약 진행 상황 관리';
COMMENT ON COLUMN network_contracts.번호 IS '계약 번호';
COMMENT ON COLUMN network_contracts.key_code IS '고유 키 코드';
COMMENT ON COLUMN network_contracts.회원사명 IS '회원사명';
COMMENT ON COLUMN network_contracts.계약완료 IS '계약 완료 상태';


-- ================================================================
-- 트리거: updated_at 자동 업데이트
-- ================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 각 테이블에 트리거 적용
CREATE TRIGGER update_subscriber_codes_updated_at BEFORE UPDATE ON subscriber_codes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_customer_addresses_updated_at BEFORE UPDATE ON customer_addresses FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sise_products_updated_at BEFORE UPDATE ON sise_products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_sise_channels_updated_at BEFORE UPDATE ON sise_channels FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_member_fee_schedule_updated_at BEFORE UPDATE ON member_fee_schedule FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_info_fee_schedule_updated_at BEFORE UPDATE ON info_fee_schedule FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_network_cost_updated_at BEFORE UPDATE ON network_cost FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_circuit_updated_at BEFORE UPDATE ON circuit FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_info_company_circuit_updated_at BEFORE UPDATE ON info_company_circuit FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_purchase_contract_updated_at BEFORE UPDATE ON purchase_contract FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_info_purchase_contract_updated_at BEFORE UPDATE ON info_purchase_contract FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_network_contracts_updated_at BEFORE UPDATE ON network_contracts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ================================================================
-- 완료
-- ================================================================
-- 모든 테이블과 인덱스 생성 완료
