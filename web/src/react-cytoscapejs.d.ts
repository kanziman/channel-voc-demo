declare module "react-cytoscapejs" {
  import type { ComponentType, CSSProperties } from "react";
  import type { ElementDefinition } from "cytoscape";

  interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    stylesheet?: unknown;
    style?: CSSProperties;
    layout?: unknown;
    cy?: (cy: unknown) => void;
    [k: string]: unknown;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
