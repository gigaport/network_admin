from django.db import models

# Create your models here.

class NetworkContract(models.Model):
    번호 = models.IntegerField(null=True, blank=True)
    key_code = models.CharField(max_length=50, null=True, blank=True)
    지역 = models.CharField(max_length=50, null=True, blank=True)
    유형 = models.CharField(max_length=50, null=True, blank=True)
    회원사명 = models.CharField(max_length=200, null=True, blank=True)
    회선분류 = models.CharField(max_length=200, null=True, blank=True)
    계약유형 = models.CharField(max_length=100, null=True, blank=True)
    안내 = models.CharField(max_length=10, null=True, blank=True)
    내부검토 = models.CharField(max_length=10, null=True, blank=True)
    계약착수 = models.CharField(max_length=10, null=True, blank=True)
    날인대기 = models.CharField(max_length=10, null=True, blank=True)
    계약완료 = models.CharField(max_length=10, null=True, blank=True)
    완료보고문서번호 = models.CharField(max_length=200, null=True, blank=True)
    계약체결일 = models.DateTimeField(null=True, blank=True)
    추가체결일 = models.DateTimeField(null=True, blank=True)
    약정기간 = models.IntegerField(null=True, blank=True)
    약정만료일 = models.DateTimeField(null=True, blank=True)
    계약금액 = models.BigIntegerField(null=True, blank=True)
    추가신청금액 = models.BigIntegerField(null=True, blank=True)
    계약금액합계 = models.BigIntegerField(null=True, blank=True)
    비고 = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'network_contracts'
        managed = False
