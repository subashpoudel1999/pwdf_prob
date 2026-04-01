"""
CLI help text for wildcat subcommands, IO folders, and dataset files
----------
IO Folders:
    folders         - Dict of IO folder descriptions

Subcommand strings:
    initialize      - Description of the "initialize" subcommand
    preprocess      - Description of the "preprocess" subcommand
    assess          - Description of the "assess" subcommand
    export          - Description of the "export" subcommand
"""

#####
# IO Folders
#####

folders = {
    "inputs": "input datasets",
    "preprocessed": "preprocessed rasters",
    "assessment": "assessment results",
    "exports": "exported results",
}

#####
# Subcommand help strings
#####

initialize = (
    "Initialize a project folder and configuration file",
    # ----------
    "Creates a folder for a wildcat project, including a configuration file and\n"
    'an empty "inputs" subfolder. By default, the configuration file will include\n'
    "the most commonly used fields. However, users can optionally select different\n"
    "configuration verbosity levels. Options include:\n"
    " \n"
    "* default: Config includes the most commonly used fields\n"
    "* full: Config includes every configurable field\n"
    "* empty: Blank config file\n"
    "* none: No config file is created\n"
    " \n"
    "Note that if the wildcat folder already exists, then it must be empty. This\n"
    "command will not overwrite an existing project.",
)

preprocess = (
    "Clean input datasets in preparation for assessment",
    # ----------
    "Cleans inputs datasets in preparation for assessment. Wildcat assessments\n"
    "require input datasets to be rasters with the same CRS, resolution, bounds,\n"
    "and alignment. This command formats inputs to meet these requirements. The\n"
    "preprocessor uses the DEM as the template CRS, resolution, and alignment.\n"
    "All preprocessed datasets will be reprojected to match this template. The\n"
    "bounds are determined using a buffered fire perimeter, so the bounds of the\n"
    "preprocessed datasets will match the bounds of this buffer exactly.\n"
    " \n"
    "The preprocessor will limit the amount of data loaded into memory when possible.\n"
    "For example, if a large raster is provided as input, then wildcat will only\n"
    "load the portion of the raster that overlaps with the buffered fire perimeter.\n"
    "Large vector feature files will be loaded in their entirety - however, only\n"
    "the portion of the dataset that overlaps the buffered fire perimeter will be\n"
    "converted to a preprocessed raster.\n"
    " \n"
    "Other tasks of the preprocessor include:\n"
    "* Converting Polygon and Point datasets to rasters\n"
    "* Estimating severity from dNBR if severity is missing\n"
    "* Checking dNBR values are scaled properly\n"
    "* Constraining dNBR values to a valid range\n"
    "* Constraining KF-factors to positive values, and\n"
    "* Building water, development, and exclusion masks from EVT data\n"
    " \n"
    'By default, the preprocessor will search for input datasets in the "inputs"\n'
    "subfolder of a wildcat project. Users can also configure the preprocessor\n"
    "to search for inputs at other paths. The preprocessor will save its results\n"
    'in the "preprocessed" subfolder, unless otherwise configured.',
)

assess = (
    "Compute a hazard assessment from preprocessed datasets",
    # ----------
    "Runs a postfire debris flow hazard assessment using preprocessed rasters.\n"
    "Estimates debris flow likelihoods and rainfall thresholds using the M1 model\n"
    "of Staley et al., 2017. Estimates potential sediment volume using the emergency \n"
    "assessment model of Gartner et al., 2014. Classifies relative hazards using the\n"
    "scheme presented in Cannon et al., 2010. (see below for reference DOIs)\n"
    "\n"
    "The assessment proceeds as follows: First, the DEM and burn severity\n"
    "are used to characterize watersheds in the region of interest. Next, the analysis\n"
    "delineates an initial stream segment network. The segments approximate the\n"
    "stream beds in their watersheds and represent the probable flow paths of any\n"
    "debris flows. The initial network is selected to only include segments whose\n"
    "catchments are (1) below a burned area, (2) sufficiently large, and (3) not\n"
    "too large (very large catchments exhibit flood-like, rather than debris flow-like,\n"
    "behavior).\n"
    " \n"
    "Next, the routine filters the network to remove segments that do not meet\n"
    "physical criteria for debris-flow risk. At-risk segments will be sufficiently\n"
    "steep, confined, and burned. By default, the routine will not remove segments\n"
    "that are (1) in the fire perimeter, or (2) would break flow continuity, regardless\n"
    "of physical characteristics. Finally, the assessment characterizes the catchments\n"
    "of the remaining segments, and uses these characterizations to implement the\n"
    "likelihood, accumulation, volume, and hazard classification models.\n"
    " \n"
    'By default, results are saved in the "assessment" subfolder, with separate\n'
    "files holding results for the segments, outlets, and terminal outlet basins.\n"
    "The output files are GeoJSON, and hold all computed data fields. Many users will\n"
    'want to use the "wildcat export" command to obtain assessment results, rather\n'
    "than these output files, as the export command can convert results to other GIS\n"
    "formats (such as shapefiles) and can help format the output data fields. As a\n"
    "rule, the assessment outputs should be treated as read-only. If they are altered,\n"
    "then the export command may fail unexpectedly.\n"
    "\n"
    "Reference DOIs:\n"
    "Staley et al., 2017: https://doi.org/10.1016/j.geomorph.2016.10.019\n"
    "Gartner et al., 2014: https://doi.org/10.1016/j.enggeo.2014.04.008\n"
    "Cannon et al., 2010: https://doi.org/10.1130/B26459.1\n",
)

export = (
    "Export assessment results to GIS file formats",
    # ----------
    "Exports assessment results to GIS file formats. Examples include Shapefiles,\n"
    "GeoJSON, GML, GeoPackage, etc. See the documentation for a complete list of\n"
    "supported formats. Stream segment results are exported as LineString features,\n"
    "outlets as Point feature, and outlet basins as Polygon features. The exported\n"
    'files will be named "segments", "outlets", and "basins", respectively.\n'
    " \n"
    "Users can use various options to select the data fields (properties) included\n"
    "in the exported files. Some commonly exported property groups include:\n"
    "  * results: Estimated likelihoods, volumes, hazards, and rainfall thresholds\n"
    "  * model inputs: Variables used to run assessment models\n"
    "  * watershed: Variables characterizing stream segment watersheds, and\n"
    "  * filters: Boolean variables used to implement filtering checks\n"
    "By default, wildcat exports results, model inputs, and watershed variables,\n"
    "and please see the documentation for a complete description of exportable\n"
    "properties.\n"
    "\n"
    "By default, the command will reorder exported properties to group related\n"
    "values. First hazard, likelihood, and volume results are group by I15 value.\n"
    "Rainfall thresholds are grouped by rainfall duration, then by probability level.\n"
    "Then model inputs, watershed variables, and finally filter checks. The command\n"
    "also replaces hazard parameter indices with simplified values in exported\n"
    "property names. In addition to this default renaming, users can specify custom\n"
    "names for exported properties using renaming options.\n",
)
