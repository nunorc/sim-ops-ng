<script setup lang="ts">
import { computed } from 'vue';
import { parseAck } from '@/utils/ack';

const props = defineProps<{ status: string | null | undefined }>();
const stages = computed(() => parseAck(props.status));
</script>
<template>
	<span class="fw-bold">
		<template v-for="(stage, i) in stages" :key="i"><span v-if="i > 0">&nbsp;&nbsp;</span><span :class="stage.cls">{{ stage.label }}</span></template>
	</span>
</template>
