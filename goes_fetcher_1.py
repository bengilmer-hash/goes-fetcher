import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import xarray as xr
import requests
import glob
from bs4 import BeautifulSoup
from pathlib import Path

def GOES_data_fetcher(goes_version: str, first_date: datetime, num_days=1, level='l2', folder_name=None, file_name=None, rtn_path=False):
    '''
    Pulls GOES data from the two appropriate NOAA websites, which website depends on GOES version, for GOES 16 onward it pulls from 'https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes'
    otherwise it pulls from 'https://www.ncei.noaa.gov/data/goes-space-environment-monitor/access/science/xrs'

    Downloads to a folder in cwd called GOES_{level} where level is the apropriate quality level unless specified.
    File name follows the format 'g{goes_version}_d{first_date_ymd}_n{num_days}_{level}.npz' unless specified.

    Parameters
    ----------
    goes_version : string
        GOES version, must be operational for the year, see the NOAA website for GOES operational dates
    first_date : datetime
        first day of GOES data to be pulled
    num_days : int
        number of days to be pulled including the first
    level : string
        data quality level 0-2 formatted like 'l2'
    rtn_path : bool
        Returns the file path if True

    Returns
    --------
    path : string
        path to the file, only returned if rtn_path = True
    '''

    # Set up first dates in different formats for naming conventions
    first_date_ymd = first_date.strftime('%Y%m%d')

    first_date_ym = first_date.strftime('%Y/%m')

    # Assign names
    if folder_name == None:
        folder_name = f'GOES_{level}'

    if file_name == None:
        file_name = f'g{goes_version}_d{first_date_ymd}_n{num_days}_{level}.npz'

    cwd = Path.cwd()

    path = cwd / folder_name
    file = path / file_name

    if file.is_file:
        print(f'GOES data found in local directory: {path}')


    else:
        print(f'GOES data not found in local directory: {path}')
        print('Downloading from NOAA website')
        # Set up list for datasets
        ds_list = []

        # Scan through all day ranges
        for i in range(num_days):
            # Set up date
            date = first_date + timedelta(days = i)

            date_ymd = date.strftime('%Y%m%d')

            date_ym = date.strftime('%Y/%m')

            # if the XRS data file exists in the local working directory. If the file does not exist in the local working directory, it will be downloaded to the local working directory from the GOES 16-19 space weather data website.
            local_directory = './'

            # Scrape the appropriate webpage based on GOES version
            ssos_supported_goes_versions = ['16','17','18','19']

            if goes_version in ssos_supported_goes_versions: 
                ssos = True # Check 
                
                cadence = 'flx1s'

                xrs_data_website = f'https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/goes{goes_version}/{level}/data/xrsf-l2-{cadence}_science/{date_ym}/'
                xrs_filename_prefix = f'sci_xrsf-{level}-{cadence}_g{goes_version}_d{date_ymd}'


            else:
                ssos = False
                
                cadence = 'irrad'

                xrs_data_website = f'https://www.ncei.noaa.gov/data/goes-space-environment-monitor/access/science/xrs/goes{goes_version}/gxrs-l2-{cadence}_science/{date_ym}/'
                xrs_filename_prefix = f'sci_gxrs-{level}-{cadence}_g{goes_version}_d{date_ymd}'


            url = requests.get(xrs_data_website)
            
            if url.status_code == 200:
            
                url_files = BeautifulSoup(url.text, 'html.parser')
                
                for link in url_files.find_all('a'):
            
                    xrs_file = link.get('href')
            
                    if xrs_file and xrs_file.startswith(xrs_filename_prefix) and xrs_file.endswith('.nc'):
            
                        with open(local_directory + xrs_file, "wb") as f:
            
                            r = requests.get(xrs_data_website + xrs_file)
                            f.write(r.content)
                            xrs_filename = xrs_file

            # Check to make sure file was downloaded
            local_file = glob.glob(local_directory + xrs_filename_prefix + '*.nc')

            if local_file:
                print(f'Succsesfully downloaded {xrs_filename} in local working directory!')

            else:
                print(f'Something went wrong, please check file specifics')

            ds = xr.open_dataset(xrs_filename)

            ds_list.append(ds)

        if len(ds_list) == num_days:
            print('All datasets have been downloaded and opened')
        else:
            print('Something went wrong')


        # Concatenate the datasets
        ds = xr.concat(ds_list, dim='time', data_vars='minimal').sortby('time')

        # Pull datetimes and convert to seconds
        dt = ds['time'].values

        t = (dt - dt[0]) / np.timedelta64(1, "s")

        if ssos == True:
            var_names = ['xrsa_flux', 'xrsb_flux']

            flux_a = ds.variables["xrsa_flux"][:]
            flux_b = ds.variables["xrsb_flux"][:]

            dqf_a = ds['xrsa_flags']
            dqf_b = ds['xrsb_flags']


        else:
            var_names = ['a_flux', 'b_flux']

            flux_a = ds.variables["a_flux"][:]
            flux_b = ds.variables["b_flux"][:]

            dqf_a = ds['a_flags']
            dqf_b = ds['b_flags']

        bad_data_a = np.argwhere(dqf_a.values).ravel()
        bad_data_b = np.argwhere(dqf_b.values).ravel()


        flux_a = np.asarray(flux_a)
        flux_b = np.asarray(flux_b)
        time_s = np.asarray(t)
        time_dt = np.asarray(dt)

        # Create Dict
        d = {
            'flux_a': flux_a,
            'flux_b': flux_b,
            'time_s': time_s,
            'time_dt': time_dt,
            'dqfed_a': bad_data_a,
            'dqfed_b': bad_data_b
        }

        # Delete original .nc file

        file_to_delete = cwd / xrs_filename

        if file_to_delete.is_file():
            file_to_delete.unlink()
            print(f"Successfully deleted: {file_to_delete.name} from {cwd}")
        else:
            print(f"Could not delete file: file not found in current directory: {cwd}")

        # Save dict as a file in a subfolder
        subfolder = cwd / folder_name
        
        subfolder.mkdir(parents = True, exist_ok = True)

        path = subfolder / file_name
        
        np.savez(path, **d)

        print(f'Saved successfully to {path}')


    return path if rtn_path == True else None



def GOES_plot(path: str, savefig: bool = False, file_name : str = None, folder_name: str = None):
    '''
    Plots GOES data pulled via GOES_data_fetcher, does not plot without plt.show being called to prevent pre-plotting

    Parameters:
    -----------
    path : str
        the path to the GOES file
    savefig : bool
        fig will be saved if True and file_name, folder_name are not None
    file_name : str
        what the file should be named
    folder_name : str
        where the file should be saved

    Returns:
    --------
    fig
    '''
    loaded_data = np.load(path)

    restored_dict = {key: loaded_data[key] for key in loaded_data.files}

    t_dt = restored_dict['time_dt']
    t = restored_dict['time_s']
    flux_a = restored_dict['flux_a']
    flux_b = restored_dict['flux_b']
    dqfed_a = restored_dict['dqfed_a']
    dqfed_b = restored_dict['dqfed_b']

    dqf_group_a = np.array(np.split(dqfed_a, np.where(np.diff(dqfed_a) != 1)[0] + 1))
    dqf_group_b = np.array(np.split(dqfed_b, np.where(np.diff(dqfed_b) != 1)[0] + 1))


    # Vstack for simplicity and establish label lists
    fluxes = [flux_a, flux_b]
    dqf_groups = [dqf_group_a, dqf_group_b]

    flux_labels = [r'.5-4 $\AA$', r'1-8 $\AA$']
    dqf_labels = [r".5-4 $\AA$ NAN Region", r"1-8 $\AA$ NAN Region"]
    color_list = ['red', 'blue']

    # Set nans to 0
    nans_list = [False, False]

    for i in range(2):
        if np.isnan(fluxes[i]).sum() != 0:
            print(np.isnan(fluxes[i]).sum())
            nan_group = np.split(np.isnan(fluxes[i]), np.where(np.diff(np.isnan(fluxes[i])) != 1)[0] + 1)
            fluxes[i][np.isnan(fluxes[i])] = np.nanmean(fluxes[i])
            nans_list[i] = True

    with plt.ioff():

        fig = plt.figure(0, figsize=[10, 7])

        for i in range(2):

            plt.plot(
                t_dt,
                fluxes[i],
                linewidth = 1,
                label = flux_labels[i],
                marker = 'o',
                linestyle = '',
                markersize = '.5'
                )


            for a, group in enumerate(dqf_groups[i]):
                bad_ts = t_dt[group]
                bad_data = fluxes[i][group]

                plt.fill_between(
                    bad_ts,
                    y1= plt.ylim()[-1],
                    y2 = plt.ylim()[0], # Fills down to the bottom of the current plot axis
                    color = color_list[i],
                    alpha = 0.15,
                    label = dqf_labels[i] if a == 0 else ""
                )


        plt.yscale("log")
        plt.legend(loc="upper right", prop={"size": 12})
        plt.xlabel("Time [UT]")
        plt.ylabel(r"X-Ray Flux [W/$m^2$]")
        plt.title(f"GOES Flux curves for {t_dt[0].astype('datetime64[us]').item().date()}")

        if savefig == True:
            subfolder = folder_name

            file_name = file_name

            dir = Path.cwd() / subfolder

            dir.mkdir(parents = True, exist_ok = True)

            path = dir / file_name

            plt.savefig(path, dpi=300, bbox_inches='tight')

        return fig


