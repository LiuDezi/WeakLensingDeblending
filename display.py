#!/usr/bin/env python
"""Display simulated images and analysis results generated by the simulate program.
"""

import math
import argparse

import numpy as np

import matplotlib.pyplot as plt
import matplotlib.collections
import matplotlib.colors
import matplotlib.cm
import matplotlib.patheffects

import galsim

import descwl

def main():
    # Initialize and parse command-line arguments.
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--verbose', action = 'store_true',
        help = 'Provide verbose output.')
    descwl.output.Reader.add_args(parser)
    parser.add_argument('--no-display', action = 'store_true',
        help = 'Do not display the image on screen.')
    parser.add_argument('-o','--output-name',type = str, default = None, metavar = 'FILE',
        help = 'Name of the output file to write.')

    select_group = parser.add_argument_group('Object selection options')
    select_group.add_argument('--galaxy', type = int, action = 'append',
        default = [ ], metavar = 'ID',
        help = 'Select the galaxy with this database ID (can be repeated).')
    select_group.add_argument('--group', type = int, action = 'append',
        default = [ ], metavar = 'ID',
        help = 'Select galaxies belonging to the group with this group ID (can be repeated).')
    select_group.add_argument('--select', type = str, action = 'append',
        default = [ ], metavar = 'CUT',
        help = 'Select objects passing the specified cut (can be repeated).')
    select_group.add_argument('--select-region', type = str,
        default = None, metavar = '[XMIN,XMAX,YMIN,YMAX]',
        help = 'Select objects within this region relative to the image center (arcsecs).')

    match_group = parser.add_argument_group('Detection catalog matching options')
    match_group.add_argument('--match-catalog', type = str,
        default = None, metavar = 'FILE',
        help = 'Name of SExtractor-compatible detection catalog to read.')
    match_group.add_argument('--match-color', type = str,
        default = 'black', metavar = 'COL',
        help = 'Matplotlib color name to use for displaying detection catalog matches.')
    match_group.add_argument('--match-info', type = str,
        default = None, metavar = 'FMT',
        help = 'String interpolation format to generate matched object annotations.')

    view_group = parser.add_argument_group('Viewing options')
    view_group.add_argument('--magnification', type = float,
        default = 1, metavar = 'MAG',
        help = 'Magnification factor to use for display.')
    view_group.add_argument('--crop', action = 'store_true',
        help = 'Crop the displayed pixels around the selected objects.')
    view_group.add_argument('--view-region', type = str,
        default = None, metavar = '[XMIN,XMAX,YMIN,YMAX]',
        help = 'Viewing region in arcsecs relative to the image center (overrides crop if set).')
    view_group.add_argument('--draw-moments', action = 'store_true',
        help = 'Draw ellipses to represent the 50%% iosophote second moments of selected objects.')
    view_group.add_argument('--info', type = str,
        default = None, metavar = 'FMT',
        help = 'String interpolation format to generate annotation labels.')
    view_group.add_argument('--no-crosshair', action = 'store_true',
        help = 'Do not draw a crosshair at the centroid of each selected object.')
    view_group.add_argument('--clip-lo-noise-fraction', type = float,
        default = 0.1, metavar = 'FRAC',
        help = 'Clip pixels with values below this fraction of the mean sky noise.')
    view_group.add_argument('--clip-hi-percentile', type = float,
        default = 90.0, metavar = 'PCT',
        help = 'Clip pixels with non-zero values above this percentile for the selected image.')
    view_group.add_argument('--hide-background', action = 'store_true',
        help = 'Do not display background pixels.')
    view_group.add_argument('--hide-selected', action = 'store_true',
        help = 'Do not overlay any selected pixels.')
    view_group.add_argument('--add-noise',type = int,default = None,metavar = 'SEED',
        help = 'Add Poisson noise using the seed provided (no noise is added unless this is set).')
    view_group.add_argument('--clip-noise',type = float,default = -1.,metavar = 'SIGMAS',
        help = 'Clip background images at this many sigmas when noise is added.')

    format_group = parser.add_argument_group('Formatting options')
    format_group.add_argument('--info-size', type = str,
        default = 'large', metavar = 'SIZE',
        help = 'Matplotlib font size specification in points or relative (small,large,...)')
    format_group.add_argument('--dpi', type = float, default = 64.,
        help = 'Number of pixels per inch to use for display.')
    format_group.add_argument('--max-view-size', type = int,
        default = 2048, metavar = 'SIZE',
        help = 'Maximum allowed pixel dimensions of displayed image.')
    format_group.add_argument('--colormap', type = str,
        default = 'YlGnBu', metavar = 'CMAP',
        help = 'Matplotlib colormap name to use for background pixel values.')
    format_group.add_argument('--highlight', type = str,
        default = 'red', metavar = 'COL',
        help = 'Matplotlib color name to use for highlighted pixel values.')
    format_group.add_argument('--crosshair-color', type = str,
        default = 'greenyellow', metavar = 'COL',
        help = 'Matplotlib color name to use for crosshairs.')
    format_group.add_argument('--ellipse-color', type = str,
        default = 'greenyellow', metavar = 'COL',
        help = 'Matplotlib color name to use for second-moment ellipses.')
    format_group.add_argument('--info-color', type = str,
        default = 'green', metavar = 'COL',
        help = 'Matplotlib color name to use for info text.')
    format_group.add_argument('--outline-color', type = str,
        default = None, metavar = 'COL',
        help = 'Matplotlib color name to use for outlining text.')

    args = parser.parse_args()

    if args.no_display and not args.output_name:
        print 'No display our output requested.'
        return 0
    if args.hide_background and args.hide_selected:
        print 'No pixels visible with --hide-background and --hide-selected.'
        return 0

    # Load the analysis results file we will display from.
    try:
        reader = descwl.output.Reader.from_args(defer_stamp_loading = True,args = args)
        results = reader.results
        if args.verbose:
            print results.survey.description()
    except RuntimeError,e:
        print str(e)
        return -1

    # Add noise, if requested.
    if args.add_noise is not None:
        results.add_noise(args.add_noise)

    # Match detected objects to simulated objects, if requested.
    if args.match_catalog:
        detected,matched,matched_indices,matched_distance = (
            results.match_sextractor(args.match_catalog))
        if args.verbose:
            print 'Matched %d of %d detected objects (median sep. = %.2f arcsecs).' % (
                np.count_nonzero(matched),len(matched),np.median(matched_distance))

    # Create region selectors.
    if args.select_region:
        try:
            assert args.select_region[0] == '[' and args.select_region[-1] == ']'
            xmin,xmax,ymin,ymax = [ float(token) for token in args.select_region[1:-1].split(',') ]
            assert xmin < xmax and ymin < ymax
        except (ValueError,AssertionError):
            print 'Invalid select-region xmin,xmax,ymin,ymax = %s.' % args.select_region
            return -1
        args.select.extend(['dx>=%f'%xmin,'dx<%f'%xmax,'dy>=%f'%ymin,'dy<%f'%ymax])

    # Perform object selection.
    if args.select:
        # Combine select clauses with logical AND.
        selection = results.select(*args.select,mode='and',format='mask')
    else:
        # Nothing is selected by default.
        selection = results.select('NONE',format='mask')
    # Add any specified groups to the selection with logical OR.
    for identifier in args.group:
        selected = results.select('grp_id==%d' % identifier,format='mask')
        if not np.any(selected):
            print 'WARNING: no group found with ID %d.' % identifier
        selection = np.logical_or(selection,selected)
    # Add any specified galaxies to the selection with logical OR.
    for identifier in args.galaxy:
        selected = results.select('db_id==%d' % identifier,format='mask')
        if not np.any(selected):
            print 'WARNING: no galaxy found with ID %d.' % identifier
        selection = np.logical_or(selection,selected)
    selected_indices = np.arange(results.num_objects)[selection]
    if args.verbose:
        print 'Selected IDs:\n%s' % np.array(results.table['db_id'][selected_indices])

    # Do we have individual objects available for selection in the output file?
    if np.any(selection) and not results.stamps:
        print 'Cannot display selected objects without any stamps available.'
        return -1

    # Build the image of selected objects (might be None).
    selected_image = results.get_subimage(selected_indices)

    # Calculate our viewing bounds as (xmin,xmax,ymin,ymax) in floating-point pixels
    # relative to the image bottom-left corner. Also calculate view_bounds with
    # integer values that determine how to extract sub-images to display.
    scale = results.survey.pixel_scale
    if args.view_region is not None:
        try:
            assert args.view_region[0] == '[' and args.view_region[-1] == ']'
            xmin,xmax,ymin,ymax = [ float(token) for token in args.view_region[1:-1].split(',') ]
            assert xmin < xmax and ymin < ymax
        except (ValueError,AssertionError):
            print 'Invalid view-window xmin,xmax,ymin,ymax = %s.' % args.view_region
            return -1
        # Convert to pixels relative to bottom-left corner.
        xmin = xmin/scale + 0.5*results.survey.image_width
        xmax = xmax/scale + 0.5*results.survey.image_width
        ymin = ymin/scale + 0.5*results.survey.image_height
        ymax = ymax/scale + 0.5*results.survey.image_height
        # Calculate integer pixel bounds that cover the view window.
        view_bounds = galsim.BoundsI(
            int(math.floor(xmin)),int(math.ceil(xmax))-1,
            int(math.floor(ymin)),int(math.ceil(ymax))-1)
    elif args.crop and selected_image is not None:
        view_bounds = selected_image.bounds
        xmin,xmax,ymin,ymax = (
            view_bounds.xmin,view_bounds.xmax+1,view_bounds.ymin,view_bounds.ymax+1)
    else:
        view_bounds = results.survey.image.bounds
        xmin,xmax,ymin,ymax = 0,results.survey.image_width,0,results.survey.image_height
    if args.verbose:
        vxmin = (xmin - 0.5*results.survey.image_width)*scale
        vxmax = (xmax - 0.5*results.survey.image_width)*scale
        vymin = (ymin - 0.5*results.survey.image_height)*scale
        vymax = (ymax - 0.5*results.survey.image_height)*scale
        print 'View window is [xmin,xmax,ymin,ymax] = [%.2f,%.2f,%.2f,%.2f] arcsecs' % (
            vxmin,vxmax,vymin,vymax)
        print 'View pixels in %r' % view_bounds

    # Initialize a matplotlib figure to display our view bounds.
    view_width = float(xmax - xmin)
    view_height = float(ymax - ymin)
    if (view_width*args.magnification > args.max_view_size or
        view_height*args.magnification > args.max_view_size):
        print 'Requested view dimensions %d x %d too big. Increase --max-view-size if necessary.' % (
            view_width*args.magnification,view_height*args.magnification)
        return -1
    fig_height = args.magnification*(view_height/args.dpi)
    fig_width = args.magnification*(view_width/args.dpi)
    figure = plt.figure(figsize = (fig_width,fig_height),frameon = False,dpi = args.dpi)
    axes = plt.Axes(figure, [0., 0., 1., 1.])
    axes.axis(xmin = xmin,xmax = xmax,ymin = ymin,ymax = ymax)
    axes.set_axis_off()
    figure.add_axes(axes)

    # Get the background and highlighted images to display, sized to our view.
    background = galsim.Image(bounds = view_bounds,dtype = np.float32,scale = scale)
    highlighted = background.copy()
    if not args.hide_background:
        overlap = results.survey.image.bounds & view_bounds
        if overlap.area() > 0:
            background[overlap] = results.survey.image[overlap]
    if not args.hide_selected and selected_image is not None:
        overlap = selected_image.bounds & view_bounds
        if overlap.area() > 0:
            highlighted[overlap] = selected_image[overlap]
    if np.count_nonzero(highlighted.array) == 0:
        if args.hide_background or np.count_nonzero(background.array) == 0:
            print 'There are no non-zero pixel values in the view window.'
            return -1

    # Prepare the z scaling.
    zscale_pixels = results.survey.image.array
    if selected_image:
        if selected_image.bounds.area() < 16:
            print 'WARNING: using full image for z-scaling since only %d pixel(s) selected.' % (
                selected_image.bounds.area())
        else:
            zscale_pixels = selected_image.array
    # Clip large fluxes to a fixed percentile of the non-zero selected pixel values.
    non_zero_pixels = (zscale_pixels != 0)
    vmax = np.percentile(zscale_pixels[non_zero_pixels],q = (args.clip_hi_percentile))
    # Clip small fluxes to a fixed fraction of the mean sky noise.
    vmin = args.clip_lo_noise_fraction*np.sqrt(results.survey.mean_sky_level)
    if args.verbose:
        print 'Clipping pixel values to [%.1f,%.1f] detected electrons.' % (vmin,vmax)

    # Define the z scaling function. See http://ds9.si.edu/ref/how.html#Scales
    def zscale(pixels):
        return np.sqrt(pixels)

    # Calculate the clipped and scaled pixel values to display.
    highlighted_z = zscale((np.clip(highlighted.array,vmin,vmax) - vmin)/(vmax-vmin))
    if args.add_noise:
        vmin = args.clip_noise*np.sqrt(results.survey.mean_sky_level)
        if args.verbose:
            print 'Background pixels with noise clipped to [%.1f,%.1f].' % (vmin,vmax)
    background_z = zscale((np.clip(background.array,vmin,vmax) - vmin)/(vmax-vmin))

    # Convert the background image to RGB using the requested colormap.
    # Drop the alpha channel [3], which is all ones anyway.
    cmap = matplotlib.cm.get_cmap(args.colormap)
    background_rgb = cmap(background_z)[:,:,:3]

    # Overlay the highlighted image using alpha blending.
    # http://en.wikipedia.org/wiki/Alpha_compositing#Alpha_blending
    if args.highlight and args.highlight != 'none':
        alpha = highlighted_z[:,:,np.newaxis]
        color = np.array(matplotlib.colors.colorConverter.to_rgb(args.highlight))
        final_rgb = alpha*color + background_rgb*(1.-alpha)
    else:
        final_rgb = background_rgb

    # Draw the composite image.
    extent = (view_bounds.xmin,view_bounds.xmax+1,view_bounds.ymin,view_bounds.ymax+1)
    axes.imshow(final_rgb,extent = extent,aspect = 'equal',origin = 'lower',
        interpolation = 'nearest')

    # The argparse module escapes any \n or \t in string args, but we need these
    # to be unescaped in the annotation format string.
    if args.info:
        args.info = args.info.decode('string-escape')
    if args.match_info:
        args.match_info = args.match_info.decode('string-escape')

    num_selected = len(selected_indices)
    ellipse_centers = np.empty((num_selected,2))
    ellipse_widths = np.empty(num_selected)
    ellipse_heights = np.empty(num_selected)
    ellipse_angles = np.empty(num_selected)
    match_ellipse_centers = np.empty((num_selected,2))
    match_ellipse_widths = np.empty(num_selected)
    match_ellipse_heights = np.empty(num_selected)
    match_ellipse_angles = np.empty(num_selected)
    num_match_ellipses = 0
    for index,selected in enumerate(selected_indices):
        info = results.table[selected]
        # Do we have a detected object matched to this simulated source?
        match_info = None
        if args.match_catalog and info['match'] >= 0:
            match_info = detected[info['match']]
        # Calculate the selected object's centroid position in user display coordinates.
        x_center = (0.5*results.survey.image_width + info['dx']/scale)
        y_center = (0.5*results.survey.image_height + info['dy']/scale)
        if match_info is not None:
            x_match_center = match_info['X_IMAGE']-0.5
            y_match_center = match_info['Y_IMAGE']-0.5
        # Draw a crosshair at the centroid of selected objects.
        if not args.no_crosshair:
            axes.plot(x_center,y_center,'+',color = args.crosshair_color,
                markeredgewidth = 2,markersize = 24)
            if match_info:
                axes.plot(x_match_center,y_match_center,'x',color = args.match_color,
                    markeredgewidth = 2,markersize = 24)
        # Add annotation text if requested.
        if args.info:
            path_effects = None if args.outline_color is None else [
                matplotlib.patheffects.withStroke(linewidth = 2,
                foreground = args.outline_color)]
            try:
                annotation = args.info % info
            except IndexError:
                print 'Invalid annotate-format %r' % args.info
                return -1
            axes.annotate(annotation,xy = (x_center,y_center),xytext = (4,4),
                textcoords = 'offset points',color = args.info_color,
                fontsize = args.info_size,path_effects = path_effects)
        if match_info and args.match_info:
            path_effects = None if args.outline_color is None else [
                matplotlib.patheffects.withStroke(linewidth = 2,
                foreground = args.outline_color)]
            try:
                annotation = args.match_info % match_info
            except IndexError:
                print 'Invalid match-format %r' % args.match_info
                return -1
            axes.annotate(annotation,xy = (x_match_center,y_match_center),
                xytext = (4,4),textcoords = 'offset points',
                color = args.info_color,fontsize = args.info_size,
                path_effects = path_effects)
        # Add a second-moments ellipse if requested.
        if args.draw_moments:
            ellipse_centers[index] = (x_center,y_center)
            ellipse_widths[index] = info['a']/scale
            ellipse_heights[index] = info['b']/scale
            ellipse_angles[index] = np.degrees(info['beta'])
            if match_info:
                # This will only work if we have the necessary additional fields in the match catalog.
                try:
                    match_ellipse_centers[num_match_ellipses] = (x_match_center,y_match_center)
                    match_ellipse_widths[num_match_ellipses] = match_info['A_IMAGE']
                    match_ellipse_heights[num_match_ellipses] = match_info['B_IMAGE']
                    match_ellipse_angles[num_match_ellipses] = match_info['THETA_IMAGE']
                    num_match_ellipses += 1
                except IndexError:
                    pass

    # Draw any ellipses.
    if args.draw_moments:
        ellipses = matplotlib.collections.EllipseCollection(units = 'x',
            widths = ellipse_widths,heights = ellipse_heights,angles = ellipse_angles,
            offsets = ellipse_centers, transOffset = axes.transData)
        ellipses.set_facecolor('none')
        ellipses.set_edgecolor(args.ellipse_color)
        axes.add_collection(ellipses,autolim = True)
        if num_match_ellipses > 0:
            ellipses = matplotlib.collections.EllipseCollection(units = 'x',
                widths = match_ellipse_widths,heights = match_ellipse_heights,
                angles = match_ellipse_angles,offsets = match_ellipse_centers,
                transOffset = axes.transData)
            ellipses.set_facecolor('none')
            ellipses.set_edgecolor(args.match_color)
            #ellipses.set_linestyle('dashed')
            axes.add_collection(ellipses,autolim = True)

    if args.output_name:
        figure.savefig(args.output_name,dpi = args.dpi)

    if not args.no_display:
        plt.show()

if __name__ == '__main__':
    main()
