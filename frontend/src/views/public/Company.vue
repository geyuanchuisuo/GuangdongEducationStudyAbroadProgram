<script setup lang="ts">
import SectionTitle from '../../components/SectionTitle.vue'
</script>

<template>
  <div class="page-wrap">
    <SectionTitle eyebrow="ABOUT YUEJIAO" title="关于粤教服务" desc="创办于1981年，持续建设专业、可靠的文化教育综合服务平台。" />
    <section class="company-hero surface">
      <div><span class="badge">省属国有优质教育服务品牌</span><h2>致力让生活更美好</h2><p>广东省教育服务有限公司简称“粤教服务”，2024年3月划转至广东教育国际交流服务中心有限公司。公司聚焦国际教育、智慧教育、素质教育和实体教育，整合优质教育资源，为广东教育事业和国际化人才培养提供服务。</p></div>
      <div class="company-numbers"><div><b>1981</b><span>创办年份</span></div><div><b>4</b><span>核心业务板块</span></div><div><b>300+</b><span>合作院校资源</span></div></div>
    </section>
    <section class="values section-block">
      <article><b>向上向善</b><p>以社会责任和健全人格作为长期发展的精神指引。</p></article>
      <article><b>实干笃行</b><p>学而能用、知而能行，把专业能力落实到每一个服务节点。</p></article>
      <article><b>全球视野</b><p>连接国内外优质教育资源，培养具备跨文化能力的人才。</p></article>
      <article><b>客户至上</b><p>基于真实需求提供个性化、透明、可持续的教育方案。</p></article>
    </section>
    <section class="section-block">
      <SectionTitle eyebrow="BUSINESS MAP" title="主营业务与部门" />
      <div class="business-table surface">
        <div><b>国际教育</b><p>德国双元制、新加坡国际本硕、全球留学、国际研学</p></div>
        <div><b>智慧教育</b><p>智慧校园、教育信息化、AI 助教、实验室建设</p></div>
        <div><b>素质教育</b><p>课后服务、STEAM、非遗文化、体育与心理健康</p></div>
        <div><b>实体教育</b><p>研学服务、科技赛事、职业教育和人才培养项目</p></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.company-hero { display: grid; grid-template-columns: 1.25fr .75fr; gap: 38px; padding: 46px; background: #2d2b73; color: #fff; }
.company-hero h2 { margin: 22px 0 15px; font-family: Georgia, serif; font-size: 48px; }
.company-hero p { color: #d6d5ee; line-height: 2; }
.company-numbers { display: grid; gap: 14px; }
.company-numbers div { padding: 20px; border: 1px solid #555198; border-radius: 16px; }
.company-numbers b { display: block; color: #8dd933; font-size: 34px; }
.company-numbers span { color: #c7c5e4; }
.values { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.values article { padding: 26px; background: #fff; border-top: 5px solid #80b717; border-radius: 16px; }
.values article:nth-child(2) { border-color: #ffc634; }
.values article:nth-child(3) { border-color: #5a50b8; }
.values article:nth-child(4) { border-color: #f06d63; }
.values b { color: var(--ink-deep); font-size: 20px; }
.values p { color: var(--muted); line-height: 1.8; }
.business-table { display: grid; grid-template-columns: repeat(2, 1fr); }
.business-table div { padding: 28px; border: 1px solid var(--line); }
.business-table b { color: var(--ink-deep); font-size: 20px; }
.business-table p { color: var(--muted); line-height: 1.8; }
@media (max-width: 850px) { .company-hero, .values, .business-table { grid-template-columns: 1fr; } }
</style>

