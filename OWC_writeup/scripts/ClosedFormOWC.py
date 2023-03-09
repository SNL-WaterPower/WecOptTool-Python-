from datetime import datetime

import autograd.numpy as np
import capytaine as cpy
import matplotlib.pyplot as plt
from scipy.optimize import brute

import wecopttool as wot

import autograd.numpy as np

def h_poly_helper(tt):
  A = np.array([
      [1, 0, -3, 2],
      [0, 1, -2, 1],
      [0, 0, 3, -2],
      [0, 0, -1, 1]
      ], dtype=tt[-1].dtype)
  return [
    sum( A[i, j]*tt[j] for j in range(4) )
    for i in range(4) ]

def h_poly(t):
  tt = [ None for _ in range(4) ]
  tt[0] = 1
  for i in range(1, 4):
    tt[i] = tt[i-1]*t
  return h_poly_helper(tt)

def H_poly(t):
  tt = [ None for _ in range(4) ]
  tt[0] = t
  for i in range(1, 4):
    tt[i] = tt[i-1]*t*i/(i+1)
  return h_poly_helper(tt)

def interp_func(x, y):
  "Returns integral of interpolating function"
  if len(y)>1:
    m = (y[1:] - y[:-1])/(x[1:] - x[:-1])
    m = np.concatenate([m[[0]], (m[1:] + m[:-1])/2, m[[-1]]])
  def f(xs):
    if len(y)==1: # in the case of 1 point, treat as constant function
      return y[0] + np.zeros_like(xs)
    I = np.searchsorted(x[1:], xs)
    dx = (x[I+1]-x[I])
    hh = h_poly((xs-x[I])/dx)
    return hh[0]*y[I] + hh[1]*m[I]*dx + hh[2]*y[I+1] + hh[3]*m[I+1]*dx
  return f

def myinterp(x, y, xs):
    if xs.size==1:
        return interp_func(x,y)(xs)
    else:
        return [interp_func(x,y)(xs[ii]) for ii in range(xs.size)]

def interp2d(interp1d, xdata, ydata, fdata, xpt, ypt):

    yinterp = np.zeros((ydata.size,xpt.size))
    output = np.zeros((xpt.size,ypt.size)) #Array{R}(undef, nxpt, nypt)

    for i in range(ydata.size):
        yinterp[i, :] = interp1d(xdata, fdata[:, i], xpt)
    
    # yinterp = [np.array(interp1d(xdata,fdata[:, ii],xpt)) for ii in range(ydata.size)]

    for i in range(xpt.size):
        output[i, :] = interp1d(ydata, yinterp[:, i], ypt)
    
    # output = [interp1d(ydata,yinterp[:, ii],ypt) for ii in range(xpt.size)]

    return output

def brent(myf, mya, myb, atol=2e-12, rtol=4*np.finfo(float).eps, maxiter=100): # args=()

    xpre = mya; xcur = myb
    # xblk = 0.0; fblk = 0.0; spre = 0.0; scur = 0.0
    error_num = "INPROGRESS"

    fpre = myf(xpre)#, args...)
    fcur = myf(xcur)#, args...)
    xblk = np.zeros_like(fpre)
    fblk = np.zeros_like(fpre)
    spre = np.zeros_like(fpre)
    scur = np.zeros_like(fpre)
    funcalls = 2
    iterations = 0
    
    if fpre*fcur > 0:
        error_num = "SIGNERR"
        return 1e-6,error_num#, (iter=iterations, fcalls=funcalls, flag=error_num)
    
    if fpre == np.zeros_like(fpre):
        error_num = "CONVERGED"
        return xpre,error_num#, (iter=iterations, fcalls=funcalls, flag=error_num)
    
    if fcur == np.zeros_like(fcur):
        error_num = "CONVERGED"
        return xcur,error_num#, (iter=iterations, fcalls=funcalls, flag=error_num)
    

    for i in range(maxiter):
        iterations = iterations + 1
        if fpre*fcur < 0:
            xblk = xpre
            fblk = fpre
            spre = scur = xcur - xpre
        
        if np.abs(fblk) < np.abs(fcur):
            xpre = xcur
            xcur = xblk
            xblk = xpre

            fpre = fcur
            fcur = fblk
            fblk = fpre
        

        delta = (atol + rtol*np.abs(xcur))/2.0
        sbis = (xblk - xcur)/2.0
        if fcur == np.zeros_like(fcur) or np.abs(sbis) < delta:
            error_num = "CONVERGED"
            return xcur,error_num#, (iter=iterations, fcalls=funcalls, flag=error_num)
        

        if np.abs(spre) > delta and np.abs(fcur) < np.abs(fpre):
            if xpre == xblk:
                # interpolate
                stry = -fcur*(xcur - xpre)/(fcur - fpre)
            else:
                # extrapolate
                dpre = (fpre - fcur)/(xpre - xcur)
                dblk = (fblk - fcur)/(xblk - xcur)
                stry = -fcur*(fblk*dblk - fpre*dpre)/(dblk*dpre*(fblk - fpre))
            
            if 2*np.abs(stry) < np.minimum(np.abs(spre), 3*np.abs(sbis) - delta):
                # good short step
                spre = scur
                scur = stry
            else:
                # bisect
                spre = sbis
                scur = sbis
            
        else: 
            # bisect
            spre = sbis
            scur = sbis
        

        xpre = xcur; fpre = fcur
        if np.abs(scur) > delta:
            xcur = xcur + scur
        else:
            if sbis > 0:
                xcur = xcur + delta #(sbis > 0 ? delta : -delta)
            else:
                xcur = xcur - delta
        

        fcur = myf(xcur)#, args...)
        funcalls = funcalls + 1
    
    error_num = "CONVERR"
    return xcur,error_num#, (iter=iterations, fcalls=funcalls, flag=error_num)

def self_rectifying_turbine_power_internalsolve(torque,V_wec): #m/s omega_turbine_guess: ndarray, #rad/s
    # ) -> np.ndarray:#tuple[np.ndarray, np.ndarray]:
    """Calculate the turbine power.  Omega is assumed always positive (the whole point of a self rectifying turbine),
    but power can be put into the system, which for now is assumed symmetric in the performance curves.

    Parameters
    ----------
    torque
        Torque on the turbine
    V_wec
        Velocity of the wec
    """
    # len xwec is set (ndof * ncomponents (2*nfreq+1))
    # len xopt is any length and be anything, but pto module has rules about shape etc.  
    # TODO: put in self
    rho = 1.225
    blade_chord = 0.054 #m
    N_blades = 30.0
    blade_radius = 0.298/2 #m
    blade_height = (1.0-0.7)*blade_radius #m
    A_wec = 2.0 #m2
    A_turb = np.pi*blade_radius**2 #m2
    P_ambient = 101325.0 #pa (1 atm)

    # power = np.zeros_like(torque)

    # for ii in range(torque.size):
    def myinternalsolve(torque_ii,V_wec_ii):
        def OWC_turbine0(omega_turbine_guess):
            V_turb = np.abs(A_wec*V_wec_ii/A_turb) #turbine always sees velocity as positive
            power1 = np.abs(torque_ii*omega_turbine_guess)
            V_turbcompressed = V_turb#/((P_ambient+power1/(A_turb*V_turb))/P_ambient)**(1/1.401) #compressibility correction pv = nrt -> assume adiabiatic p2/p1 = (V1/V2)^specific_heat_ratio (1.401 for air for the operating temp we're at)
            
            inv_TSR_guess = V_turbcompressed/(omega_turbine_guess*blade_radius)
            if inv_TSR_guess > 1000000.0:
                inv_TSR_guess = np.array(1000000.0)

            inv_TSRdata_Ct = np.array([-1000000,
                -100,
                -10,
                -1,
                0,
                0.026828855,
                0.061012163,
                0.095195471,
                0.129390802,
                0.163601319,
                0.19783525,
                0.232095125,
                0.266361327,
                0.300659802,
                0.337110351,
                0.371665655,
                0.403564085,
                0.436495224,
                0.465399555,
                0.514548355,
                0.544918292,
                0.571192363,
                0.59270955,
                0.618927127,
                0.642745995,
                0.66620479,
                0.69188684,
                0.739707487,
                0.76472745,
                0.789742192,
                0.813204716,
                0.8366742,
                0.861685462,
                0.886707165,
                0.911725387,
                0.936747091,
                0.960198676,
                0.985222229,
                1.013346631,
                1.041475672,
                1.06804186,
                1.093049642,
                1.121175783,
                1.152420632,
                1.182099998,
                1.208656035,
                1.238318497,
                1.272654306,
                1.306992646,
                1.341322127,
                1.375644648,
                1.409964004,
                1.444286525,
                1.478596389,
                1.512902457,
                1.547211689,
                1.581516492,
                1.615813701,
                1.650105848,
                1.684399893,
                1.718689508,
                1.752971531,
                1.78725735,
                1.82154127,
                1.855813168,
                1.890090128,
                1.924355698,
                1.958615573,
                1.992872284,
                2.027130893,
                2.061392033,
                2.095648111,
                2.129901658,
                2.16414951,
                2.1983923,
                2.232637621,
                2.266882941,
                2.301128262,
                2.335369154,
                2.369611943,
                2.403853467,
                2.438098788,
                2.467671948,
                2.6,
                3,
                10,
                50,
                100,
                1000000])
            
            Ct_data = np.array([0.375722776,
                0.375722776,
                0.375722776,
                0.375722776,
                0.375722776,
                0.375722776,
                0.375722776,
                0.374275093,
                0.376102447,
                0.382066689,
                0.394408635,
                0.413817765,
                0.434950599,
                0.464874322,
                0.494891355,
                0.522413413,
                0.557058674,
                0.595505788,
                0.637675307,
                0.733645009,
                0.775246014,
                0.808599425,
                0.858889048,
                0.898233279,
                0.942662941,
                0.98307891,
                1.0176516,
                1.109300279,
                1.151661245,
                1.192600155,
                1.234031877,
                1.277359673,
                1.317350546,
                1.36018553,
                1.402072477,
                1.44490746,
                1.483359638,
                1.526698737,
                1.568074078,
                1.610713468,
                1.650948891,
                1.689991727,
                1.731841086,
                1.776591773,
                1.818222198,
                1.855692513,
                1.892718255,
                1.932811829,
                1.973594884,
                2.011964754,
                2.04843855,
                2.084050494,
                2.120524291,
                2.15355068,
                2.185542846,
                2.218396865,
                2.250044291,
                2.279623273,
                2.307823292,
                2.336540422,
                2.364050959,
                2.389493052,
                2.415969367,
                2.441928572,
                2.464612739,
                2.488675869,
                2.509636333,
                2.529045463,
                2.547592742,
                2.566657132,
                2.586411003,
                2.604785911,
                2.622471338,
                2.638605431,
                2.653360562,
                2.668805174,
                2.684249786,
                2.699694399,
                2.713932418,
                2.728687549,
                2.743097939,
                2.758542551,
                2.771242526,
                2.771242526,
                2.771242526,
                2.771242526,
                2.771242526,
                2.771242526,
                2.771242526])
            
            torque_coefficient = myinterp(inv_TSRdata_Ct,Ct_data,inv_TSR_guess)
            # torque_coefficient = 0.2962*inv_TSR**4 - 1.7108*inv_TSR**3 + 2.9842*inv_TSR**2 - 0.4105*inv_TSR + 0.3721
            omega_squared = np.abs(torque_ii)/(torque_coefficient*0.5*rho*blade_height*blade_chord*N_blades*blade_radius**3)-V_turbcompressed**2
            if omega_squared<0.0:
                omega_turbine = omega_turbine_guess
            else:
                omega_turbine = np.sqrt(omega_squared)
            
            inv_TSR = V_turbcompressed/(omega_turbine*blade_radius)
            inv_TSRdata_Ca = np.array([-1000000.0,
                -100.0,
                -50.0,
                -20.0,
                -10.0,
                0.0,
                0.012668019,
                0.03426608,
                0.045142045,
                0.057553153,
                0.071173399,
                0.085301268,
                0.097366303,
                0.118841776,
                0.129754941,
                0.139778827,
                0.158789719,
                0.169510357,
                0.179040696,
                0.19001597,
                0.20320735,
                0.217075432,
                0.235373075,
                0.243281766,
                0.261535771,
                0.276437612,
                0.28738014,
                0.309746514,
                0.314496222,
                0.330525042,
                0.346010286,
                0.35791277,
                0.39363278,
                0.426007626,
                0.432751135,
                0.448256149,
                0.472991905,
                0.49238604,
                0.506538082,
                0.522258542,
                0.541141927,
                0.559711436,
                0.587280356,
                0.603243099,
                0.623148907,
                0.643251111,
                0.66566147,
                0.680382139,
                0.702029778,
                0.72676211,
                0.75149701,
                0.778443456,
                0.802495913,
                0.830306138,
                0.859654739,
                0.890547726,
                0.921439344,
                0.953872962,
                0.987842604,
                1.021805398,
                1.055763211,
                1.089717911,
                1.123670121,
                1.157624821,
                1.191565203,
                1.225508697,
                1.259449701,
                1.293384479,
                1.327313966,
                1.361237849,
                1.395167335,
                1.429090907,
                1.463007631,
                1.496926223,
                1.530844503,
                1.564760293,
                1.598674838,
                1.632587515,
                1.666499881,
                1.700410691,
                1.734322745,
                1.768229819,
                1.802136271,
                1.836043345,
                1.869948551,
                1.903858116,
                1.937757408,
                1.971661992,
                2.005578093,
                2.039467113,
                2.073365782,
                2.107270366,
                2.14117246,
                2.175075487,
                2.208974156,
                2.242872826,
                2.276771495,
                2.310670165,
                2.344568834,
                2.378467504,
                2.412366173,
                2.446264843,
                2.480163512,
                2.503649469,
                2.509371154,
                2.65,
                2.75,
                3.0,
                4.0,
                5.0,
                7.0,
                10.0,
                20.0,
                50.0,
                100.0,
                1000000.0])

            Ca_data = np.array([0.092282521,
                0.092282521,
                0.092282521,
                0.092282521,
                0.092282521,
                0.092282521,
                0.092282521,
                0.108898362,
                0.166429569,
                0.220299948,
                0.281008945,
                0.337880945,
                0.389410575,
                0.459040664,
                0.518464217,
                0.578526192,
                0.629890894,
                0.672544117,
                0.723541827,
                0.778887736,
                0.830091701,
                0.892335842,
                0.945980007,
                0.994584051,
                1.05696206,
                1.106830028,
                1.161446822,
                1.228899216,
                1.290898399,
                1.359077526,
                1.408090836,
                1.465159246,
                1.562243494,
                1.655088735,
                1.697592835,
                1.759255085,
                1.811679549,
                1.859073611,
                1.914558511,
                1.982617847,
                2.036904363,
                2.087541557,
                2.145242742,
                2.194618208,
                2.255209854,
                2.300621402,
                2.344023427,
                2.396784052,
                2.445120045,
                2.495353764,
                2.547230542,
                2.59005665,
                2.643459039,
                2.691239423,
                2.737428015,
                2.785870789,
                2.833437265,
                2.88173104,
                2.92692827,
                2.967744011,
                3.005373215,
                3.041010834,
                3.075055183,
                3.110692802,
                3.137169126,
                3.165637035,
                3.192511676,
                3.215403146,
                3.23490892,
                3.250829839,
                3.270335613,
                3.286057374,
                3.297397646,
                3.30993287,
                3.322268935,
                3.333011731,
                3.342957894,
                3.351709104,
                3.360261157,
                3.367817416,
                3.37617031,
                3.381336666,
                3.386104705,
                3.391271062,
                3.395242467,
                3.402002092,
                3.402189484,
                3.405762572,
                3.4066704527,
                3.410319686,
                3.410108761,
                3.413681849,
                3.415661668,
                3.418238963,
                3.418028038,
                3.417817113,
                3.417606188,
                3.417395263,
                3.417184338,
                3.416973413,
                3.416762488,
                3.416551563,
                3.416340638,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823,
                3.408526823])
            
            if inv_TSR > 1000000.0:
                inv_TSR = np.array(1000000.0)
        
            Ca_used = myinterp(inv_TSRdata_Ca,Ca_data,inv_TSR)
            # Ca_used = 0.4093*inv_TSR**3 - 2.5095*inv_TSR**2 + 5.1228*inv_TSR - 0.0864
            flowrate_turb = V_turbcompressed*A_turb
            flowrate_wec = A_wec*V_wec_ii

            deltaP_turb = Ca_used/flowrate_turb*0.5*rho*blade_height*blade_chord*N_blades*V_turbcompressed*(V_turbcompressed**2+(omega_turbine*blade_radius)**2)
            deltaP_wec = deltaP_turb*flowrate_turb/flowrate_wec
            force_wec = deltaP_wec*A_wec

            V_turbcompressed2 = V_turb#/((P_ambient+deltaP_turb)/P_ambient)**(1/1.401) #compressibility correction pv = nrt -> assume adiabiatic p2/p1 = (V1/V2)^specific_heat_ratio (1.401 for air for the operating temp we're at)
            # print(V_turbcompressed-V_turbcompressed2)
            power2 = Ca_used*0.5*rho*(V_turbcompressed**2+(omega_turbine*blade_radius)**2)*blade_height*blade_chord*N_blades*V_turbcompressed

            OWCresidual = omega_turbine_guess-omega_turbine
            return OWCresidual, power2*np.sign(torque_ii), force_wec

        def OWC_turbine_deltaP(omega_turbine_guess):
            OWCresidual, power2, force_wec = OWC_turbine0(omega_turbine_guess)
            return force_wec

        def OWC_turbine2(omega_turbine_guess):
            OWCresidual, power2, force_wec = OWC_turbine0(omega_turbine_guess)
            return power2

        def OWC_turbine(omega_turbine_guess):
            OWCresidual, power2, force_wec = OWC_turbine0(omega_turbine_guess)
            return OWCresidual

        omega_star_ii,error_num = brent(OWC_turbine,0.1,1e4) #rad/s, which is approx 1.0-100,000.0 RPM

        if error_num == "SIGNERR": #Try again with shifted bounds
            omega_star_ii,error_num = brent(OWC_turbine,1e4,1e8) #rad/s, which is approx 100k-1000000k RPM

        if error_num == "SIGNERR":
            print(error_num)
            print(torque_ii)
            print(V_wec_ii)
            power_ii = 0.0
        else:
            # power_ii = OWC_turbine2(omega_star_ii)
            power_ii = OWC_turbine_deltaP(omega_star_ii)
        
        return power_ii
    power = [myinternalsolve(torque[ii],V_wec[ii]) for ii in range(torque.size)]
    return power


if __name__ == "__main__":
    import matplotlib.pyplot as plt # for plotting
    import time
    import pickle

    nx = 21
    ny = 22
    torque = np.linspace(1.0, 100, nx)
    V_wec = np.linspace(1.0, 10, ny)
    power = np.zeros((nx,ny))
    torquegrid = np.zeros((nx,ny))
    V_wecgrid = np.zeros((nx,ny))
    start = time.time()
    for i_V_wec in range(ny):
        V_wec2 = np.zeros(ny)+V_wec[i_V_wec]
        power[:,i_V_wec] = self_rectifying_turbine_power_internalsolve(torque,V_wec2)
        torquegrid[:,i_V_wec] = torque
        for i_torque in range (nx):
            V_wecgrid[i_torque,i_V_wec] = V_wec[i_V_wec]

    end = time.time()
    print("Calculation Time")
    print(end - start)

    # Save Precalculated Data
    pickle.dump((torque, V_wec,power), open('power_coarse.p', 'wb'))
    savedtorque, savedV_wec, savedpower = pickle.load(open('power_coarse.p', 'rb'))

    nx = 30
    ny = 31
    start = time.time()
    newtorque = np.linspace(1.0, 100, nx)
    newVwec = np.linspace(1.0, 10, ny)
    testout = interp2d(myinterp, torque, V_wec, power, newtorque, newVwec)
    end = time.time()
    print("Interp Time")
    print(end - start)


    # Make new grid points for plotting
    torquegrid2 = np.zeros((nx,ny))
    V_wecgrid2 = np.zeros((nx,ny))
    for i_V_wec in range(ny):
        torquegrid2[:,i_V_wec] = newtorque
        for i_torque in range (nx):
            V_wecgrid2[i_torque,i_V_wec] = newVwec[i_V_wec]


    #   Ys = integ(x, y, xs)
    # P.plot(torque, power, label='Torque', color='blue')
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.scatter(torquegrid,V_wecgrid,power,marker='.',label='Force')
    # ax.scatter(torquegrid,V_wecgrid,savedForce,marker='.',label='ForceSaved')
    ax.scatter(torquegrid2,V_wecgrid2,testout,marker='.',label='ForceInterp')
    ax.set_xlabel('Torque')
    ax.set_ylabel('Velocity')
    ax.set_zlabel('Force')
    plt.legend()
    plt.show()
    # print(len(power))