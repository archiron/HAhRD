import tensorflow as tf
import sys
import os

#Directly using the package
from CNN_Module.utils.conv2d_utils import *
from CNN_Module.utils.conv3d_utils import *

def calculate_model_accuracy(Z,Y):
    '''
    DESCRIPTION:
        This function will be used to calculate the model accuracy.
        Both regression accuracy and classification accuracy
        will be displayed separately in the tensorboard.
        This formulation of accuracy will be unique for each
        model description.
    USAGE:
        INPUT:
            Z   :the activation from the final layer of the model
            Y   :the target label of the model to aim at (Arjun)
        OUPUT:
            regression_accuracy     : 100- (% error)(WRONG, Think better metric)
            classification_accuracy : (correct/total)*100

            These output will be optionally caught by the caller
            if we want to display them in the terminal also and
            then run in the ops along with losses.
    '''
    with tf.name_scope('accuracy_calculation'):
        #Regression accuracy calcuation as 100-%error
        #Energy_accuracy/error
        energy_abs_diff=tf.losses.absolute_difference(Z[:,0],
                                    Y[:,0],reduction=tf.losses.Reduction.NONE)
        energy_error=(tf.reduce_mean(tf.divide(
                                energy_abs_diff,Y[:,0]+1e-10)))*100
        tf.summary.scalar('percentage_energy_error',energy_error)

        #Eta Accuracy/Error
        # eta_abs_diff=tf.losses.absolute_difference(Z[:,1],
        #                             Y[:,1],reduction=tf.losses.Reduction.NONE)
        # eta_error=(tf.reduce_mean(tf.abs(tf.divide(
        #                             eta_abs_diff,Y[:,1]+1e-10))))*100
        # tf.summary.scalar('percentage_eta_error',eta_error)

        #Phi Accuracy/Error
        # phi_abs_diff=tf.losses.absolute_difference(Z[:,2],
        #                             Y[:,2],reduction=tf.losses.Reduction.NONE)
        # phi_error=(tf.reduce_mean(tf.abs(tf.divide(
        #                             phi_abs_diff,Y[:,2]+1e-10))))*100
        # tf.summary.scalar('percentage_phi_error',phi_error)


        #Calculation of Classification error
        regression_len=1        #from where classification label starts in prediction
        regression_label_len=3  #from where classification label starts in labels
        prediction=tf.argmax(Z[:,regression_len:],axis=1)
        label=tf.argmax(Y[:,regression_label_len:],axis=1)

        correct=tf.equal(prediction,label)
        classification_accuracy=tf.reduce_mean(tf.cast(correct,'float'))*100
        tf.summary.scalar('percentage_classification_accuracy',classification_accuracy)

    #Returning the accuracy tuple to be used in inference module
    accuracy_tuple=(energy_error,
                    classification_accuracy)
    return accuracy_tuple


def calculate_total_loss(Z,Y,scope=None):
    '''
    DESCRIPTION:
        This function combines all the losses i.e the model loss
        + L2Regularization loss

        Also, it will filter the L2 loss based on the namescope
        from all_losses collection to give specific loss for
        each GPU.
        (Though the L2Loss will be same for both GPU, but both
        GPU need to calculate their complete loss for computing
        gradient, so its better to do it from their local copy
        of variables)
    USAGE:
        INPUT:
            Z       :the final layer's unnormalized output of model
            Y       :the actual target label to train model on
            scope   :the namescope of the current tower to compute
                        the tower specific loss from the local copy
                        of the parameter present on each tower.
        OUTPUT:
            total_cost: the total cost of the model, which will be
                        used to calculate the gradient
    '''
    with tf.name_scope('loss_calculation'):
        #A list to combine all losses
        all_loss_list=[]

        #Calculating the L2_loss(scalar)
        reg_loss_list=tf.get_collection('all_losses',scope=scope)
        l2_reg_loss=0.0
        if not len(reg_loss_list)==0:
            l2_reg_loss=tf.add_n(reg_loss_list,name='l2_reg_loss')
            tf.summary.scalar('l2_reg_loss',l2_reg_loss)
        all_loss_list.append(l2_reg_loss)

        #Calculating the model loss
        #Calculating the regression loss(scalar)
        regression_len=1
        regression_output=Z[:,0:regression_len]#0,1,2
        regression_label=Y[:,0:regression_len]#TRUTH

        #mean_squared_error Regrassion Loss
        regression_loss=tf.losses.mean_squared_error(regression_output,
                                    regression_label)

        #Defining new loss based on the Mean Percentage Error
        # absolute_diff=tf.losses.absolute_difference(regression_output,
        #                                             regression_label,
        #                                 reduction=tf.losses.Reduction.NONE)
        # regression_loss=tf.reduce_mean(tf.abs(tf.divide(
        #                         absolute_diff,regression_label+1e-10)))*100

        tf.summary.scalar('regression_loss',regression_loss)
        all_loss_list.append(regression_loss)

        #Calculating the x-entropy loss(scalar)
        regression_label_len=3
        class_output=Z[:,regression_len:]#3,4,....
        class_label=Y[:,regression_label_len:]#TRUTH
        categorical_loss=tf.losses.softmax_cross_entropy(class_label,
                                                        class_output)
        tf.summary.scalar('categorical_loss',categorical_loss)
        all_loss_list.append(categorical_loss)

        #calculating the total loss
        total_loss=tf.add_n(all_loss_list,name='merge_loss')
        tf.summary.scalar('total_loss',total_loss)

    return total_loss

def model3(X,is_training):
    '''
    DESCRIPTION:
        This model is based on the importsnce of global view
        for the prediction of variable: energy, phi eta.
        All these feature for our regression task is heavily
        dependent on the having information of whole depth at once.

        1.Energy: since the energy of particle is left in the whole
                    depth as the particle penetrates the depth of
                    detector.
        This function is very similar to the model2 but this
        will only do the regression on the energy output
    USAGE:
        INPUT:
            X           : the input hits "image" to the model
            is_training : the flag to be used by batchnorm and
                            dropout for knowing whether we are in
                            training phase or testing.
        OUPUT:
            Zx          : the unnormalized and unrectified output
                            of the defined model
    '''
    #Model Hyperparameter
    bn_decision=False
    lambd=0.0
    dropout_rate=0.0

    #Reshaping the image to add the channel axis
    X_img=tf.expand_dims(X,axis=-1,name='add_channel_dim')

    #Starting the model definition
    #Adding the first layer which give the model a global view
    A1=rectified_conv3d(X_img,
                        name='conv3d1',
                        filter_shape=(3,3,40),
                        output_channel=10,
                        stride=(1,1,1),
                        padding_type='VALID',
                        is_training=is_training,
                        dropout_rate=dropout_rate,
                        apply_batchnorm=bn_decision,
                        weight_decay=lambd,
                        apply_relu=True)#it is default no need to write
    A1Mp=max_pooling3d(A1,
                        name='mpool1',
                        filter_shape=(2,2,1),
                        stride=(2,2,1),
                        padding_type='VALID')

    #Adding the second layer
    A2=rectified_conv3d(A1Mp,
                        name='conv3d2',
                        filter_shape=(3,3,1),
                        output_channel=20,
                        stride=(1,1,1),
                        padding_type='SAME',
                        is_training=is_training,
                        dropout_rate=dropout_rate,
                        apply_batchnorm=bn_decision,
                        weight_decay=lambd,
                        apply_relu=True)
    A2Mp=max_pooling3d(A2,
                        name='mpool2',
                        filter_shape=(2,2,1),
                        stride=(2,2,1),
                        padding_type='VALID')

    #Adding the third layer (repeating the same pattern)
    A3=rectified_conv3d(A2Mp,
                        name='conv3d3',
                        filter_shape=(3,3,1),
                        output_channel=30,
                        stride=(1,1,1),
                        padding_type='SAME',
                        is_training=is_training,
                        dropout_rate=dropout_rate,
                        apply_batchnorm=bn_decision,
                        weight_decay=lambd,
                        apply_relu=True)
    A3Mp=max_pooling3d(A3,
                        name='mpool3',
                        filter_shape=(2,2,1),
                        stride=(2,2,1),
                        padding_type='VALID')

    #Adding the fourth layer (repeating the same patter as above)
    A4=rectified_conv3d(A3Mp,
                        name='conv3d4',
                        filter_shape=(3,3,1),
                        output_channel=40,
                        stride=(1,1,1),
                        padding_type='SAME',
                        is_training=is_training,
                        dropout_rate=dropout_rate,
                        apply_batchnorm=bn_decision,
                        weight_decay=lambd,
                        apply_relu=True)
    A4Mp=max_pooling3d(A4,
                        name='mpool4',
                        filter_shape=(2,2,1),
                        stride=(2,2,1),
                        padding_type='VALID')

    #Adding the fifth layer (repeating the same pattern)
    A5=rectified_conv3d(A4Mp,
                        name='conv3d5',
                        filter_shape=(3,3,1),
                        output_channel=40,
                        stride=(1,1,1),
                        padding_type='SAME',
                        is_training=is_training,
                        dropout_rate=dropout_rate,
                        apply_batchnorm=bn_decision,
                        weight_decay=lambd,
                        apply_relu=True)
    A5Mp=max_pooling3d(A5,
                        name='mpool5',
                        filter_shape=(2,2,1),
                        stride=(2,2,1),
                        padding_type='VALID')

    #Finally flattening and adding a fully connected layer
    A6=simple_fully_connected(A5Mp,
                                name='fc1',
                                output_dim=50,
                                is_training=is_training,
                                dropout_rate=dropout_rate,
                                apply_batchnorm=bn_decision,
                                weight_decay=lambd,
                                flatten_first=True,
                                apply_relu=True)

    #Finally the prediction/output layer
    Z7=simple_fully_connected(A6,
                                name='fc2',
                                output_dim=3,
                                is_training=is_training,
                                dropout_rate=dropout_rate,
                                apply_batchnorm=False,
                                weight_decay=lambd,
                                flatten_first=False, #default
                                apply_relu=False)#unnormalized

    return Z7
