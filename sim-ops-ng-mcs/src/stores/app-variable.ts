import { defineStore } from "pinia";

// Theme values read from the CSS variables, for the charts
function generateVariables() {
	const style = getComputedStyle(document.body);
	const cssVar = (name: string) => style.getPropertyValue(name).trim();

	return {
		font: {
			bodyFontFamily: cssVar('--bs-body-font-family'),
			bodyFontWeight: cssVar('--bs-body-font-weight')
		},
		color: {
			theme: cssVar('--bs-theme'),
			bodyColor: cssVar('--bs-body-color'),
			borderColor: cssVar('--bs-border-color')
		}
	};
}

export const useAppVariableStore = defineStore("appVariable", () => {
  return generateVariables();
});
