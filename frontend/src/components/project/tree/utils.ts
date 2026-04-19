import type { Priority, TreeSection, TreeSuite } from "../../../types/testing";
import type { DeleteImpactSummary, TreeSelection } from "../../../types/tree";

function matchesText(value: string, search: string) {
  return value.toLowerCase().includes(search.toLowerCase());
}

export function filterSections(sections: TreeSection[], search: string): TreeSection[] {
  return sections
    .map((section) => {
      const filteredChildren = filterSections(section.children, search);
      const filteredScenarios = section.scenarios.filter((scenario) =>
        matchesText(scenario.title, search)
      );
      const sectionMatches = matchesText(section.name, search);

      if (!sectionMatches && filteredChildren.length === 0 && filteredScenarios.length === 0) {
        return null;
      }

      return {
        ...section,
        children: sectionMatches ? section.children : filteredChildren,
        scenarios: sectionMatches ? section.scenarios : filteredScenarios,
      };
    })
    .filter(Boolean) as TreeSection[];
}

export function filterTreeSuites(suites: TreeSuite[], query: string) {
  const search = query.trim().toLowerCase();
  if (!search) {
    return suites;
  }

  return suites
    .map((suite) => ({
      ...suite,
      sections: matchesText(suite.name, search) ? suite.sections : filterSections(suite.sections, search),
    }))
    .filter((suite) => suite.sections.length > 0 || matchesText(suite.name, search));
}

export function designStatusTone(status: string) {
  if (status === "approved") return "bg-emerald-500";
  if (status === "in_review") return "bg-blue-500";
  if (status === "archived") return "bg-slate-300";
  return "bg-amber-400";
}

export function automationTone(status: string) {
  if (status === "automated") return "bg-emerald-500";
  if (status === "in_progress") return "bg-orange-400";
  return "bg-slate-300";
}

export function resultTone(status: string | null) {
  if (status === "passed") return "bg-emerald-500";
  if (status === "failed") return "bg-red-500";
  if (status === "error") return "bg-orange-500";
  if (status === "skipped") return "bg-slate-400";
  return "bg-slate-200";
}

export function priorityTone(priority: Priority) {
  if (priority === "critical") return "bg-red-500";
  if (priority === "high") return "bg-orange-500";
  if (priority === "medium") return "bg-blue-500";
  return "bg-slate-300";
}

export function getSectionTreeCaseCount(section: TreeSection): number {
  const directCaseCount =
    section.counts.case_count ??
    section.scenarios.reduce((total, scenario) => total + scenario.case_count, 0);

  return (
    directCaseCount +
    section.children.reduce((total, child) => total + getSectionTreeCaseCount(child), 0)
  );
}

function summarizeSection(section: TreeSection): Required<DeleteImpactSummary> {
  const directScenarioCount = section.scenarios.length;
  const directCaseCount =
    section.counts.case_count ??
    section.scenarios.reduce((total, scenario) => total + scenario.case_count, 0);

  return section.children.reduce<Required<DeleteImpactSummary>>(
    (summary, child) => {
      const childSummary = summarizeSection(child);
      return {
        sectionCount: summary.sectionCount + childSummary.sectionCount,
        childSectionCount: summary.childSectionCount + childSummary.sectionCount,
        scenarioCount: summary.scenarioCount + childSummary.scenarioCount,
        caseCount: summary.caseCount + childSummary.caseCount,
      };
    },
    {
      sectionCount: 1,
      childSectionCount: 0,
      scenarioCount: directScenarioCount,
      caseCount: directCaseCount,
    }
  );
}

function collectSectionScenarioIds(section: TreeSection, ids = new Set<string>()) {
  for (const scenario of section.scenarios) {
    ids.add(scenario.id);
  }
  for (const child of section.children) {
    collectSectionScenarioIds(child, ids);
  }
  return ids;
}

function collectSectionIds(section: TreeSection, ids = new Set<string>()) {
  ids.add(section.id);
  for (const child of section.children) {
    collectSectionIds(child, ids);
  }
  return ids;
}

export function buildSuiteDeleteImpact(suite: TreeSuite): DeleteImpactSummary {
  return {
    sectionCount: suite.counts.section_count ?? suite.sections.length,
    scenarioCount:
      suite.counts.scenario_count ??
      suite.sections.reduce((total, section) => total + summarizeSection(section).scenarioCount, 0),
    caseCount:
      suite.counts.case_count ??
      suite.sections.reduce((total, section) => total + summarizeSection(section).caseCount, 0),
  };
}

export function buildSectionDeleteImpact(section: TreeSection): DeleteImpactSummary {
  const summary = summarizeSection(section);
  return {
    childSectionCount: Math.max(summary.sectionCount - 1, 0),
    scenarioCount: summary.scenarioCount,
    caseCount: summary.caseCount,
  };
}

export function buildScenarioDeleteImpact(caseCount: number): DeleteImpactSummary {
  return { caseCount };
}

export function buildCaseDeleteImpact(): DeleteImpactSummary {
  return {};
}

export function selectionBelongsToSection(selection: TreeSelection | null, section: TreeSection) {
  if (!selection) {
    return false;
  }

  if (selection.type === "section") {
    return collectSectionIds(section).has(selection.id);
  }

  const scenarioIds = collectSectionScenarioIds(section);
  if (selection.type === "scenario") {
    return scenarioIds.has(selection.id);
  }

  return Boolean(selection.parentId && scenarioIds.has(selection.parentId));
}

export function selectionBelongsToSuite(selection: TreeSelection | null, suite: TreeSuite) {
  if (!selection) {
    return false;
  }

  if (selection.type === "suite") {
    return selection.id === suite.id;
  }

  return suite.sections.some((section) => selectionBelongsToSection(selection, section));
}
